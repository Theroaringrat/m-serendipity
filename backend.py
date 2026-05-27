import json
import os

import toml
import streamlit as st
from langchain_chroma import Chroma
from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langgraph.prebuilt import create_react_agent

DB_DIR = "vector_db"
DATA_PATH = "data/deep_scraped_professors.json"

SYSTEM_PROMPT = """You are an academic advisor helping University of Michigan students find the best research labs to join.

Given a student's background and interests, recommend exactly 3 professors/labs.

Follow this workflow strictly — do not deviate:
1. Call search_by_direction ONCE to get candidates
2. Call get_professor_details for ALL candidates returned by search (not just top 3)
3. After EACH get_professor_details call, immediately output one evaluation line:
   EVAL: [Name] | match 1-10 | undergrad Y/N | verdict: keep/reject | reason: one sentence
4. After all evaluations, write your final answer using only the top 3 professors marked "keep"

For each of the 3 recommended professors, explain:
- Why their research matches the student's interests
- Whether they recruit undergraduate researchers (based on their join/people pages)
- Why this lab is worth contacting

Be concise and grounded. Do not repeat tool calls."""


def load_environment():
    try:
        secrets = st.secrets
    except Exception:
        try:
            secrets = toml.load(".streamlit/secrets.toml")
        except Exception:
            secrets = {}

    for key in ("GOOGLE_API_KEY", "LANGSMITH_TRACING", "LANGSMITH_API_KEY", "LANGSMITH_PROJECT"):
        if key not in os.environ and key in secrets:
            os.environ[key] = secrets[key]


_professors_data = None
_vectorstore = None


def get_professors_data():
    global _professors_data
    if _professors_data is None:
        with open(DATA_PATH) as f:
            _professors_data = json.load(f)
    return _professors_data


def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        _vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    return _vectorstore


def _generate_queries(query: str, llm) -> list[str]:
    """Use LLM to generate alternative query formulations."""
    prompt = f"""Generate 3 alternative search queries for finding robotics professors whose research matches this topic:
"{query}"

Use different academic terminology that researchers might use to describe related work.
Output exactly 3 queries, one per line, no numbering or extra text."""

    response = llm.invoke(prompt)
    content = response.content.strip()
    variants = [q.strip() for q in content.split("\n") if q.strip()][:3]
    all_queries = [query] + variants
    print(f"  [MultiQuery] queries: {all_queries}")
    return all_queries


def _multi_query_search(query: str, llm, k: int = 6) -> list[dict]:
    """Run MMR across multiple query variants, fuse results with RRF."""
    queries = _generate_queries(query, llm)

    # RRF: professor → accumulated score (lower is better)
    rrf_scores: dict[str, float] = {}
    professor_data: dict[str, dict] = {}
    K_RRF = 60  # RRF constant

    for q in queries:
        results = _mmr_search(q, k=10)
        for rank, candidate in enumerate(results):
            name = candidate["name"]
            rrf_scores[name] = rrf_scores.get(name, 0) + 1 / (K_RRF + rank + 1)
            if name not in professor_data:
                professor_data[name] = candidate

    ranked = sorted(rrf_scores.keys(), key=lambda n: rrf_scores[n], reverse=True)
    return [professor_data[name] for name in ranked[:k]]


def _mmr_search(query: str, k: int = 6) -> list[dict]:
    """Run MMR and return list of {name, dept, snippet} dicts."""
    vectorstore = get_vectorstore()
    docs = vectorstore.max_marginal_relevance_search(
        query, k=12, fetch_k=80, lambda_mult=0.5,
        filter={"page_type": {"$in": ["research", "home"]}}
    )
    seen = set()
    results = []
    for doc in docs:
        name = doc.metadata.get("name", "Unknown")
        if name in seen:
            continue
        seen.add(name)
        if len(results) >= k:
            break
        results.append({
            "name": name,
            "dept": doc.metadata.get("department", ""),
            "snippet": doc.page_content[:500],
        })
    return results


def _grade_and_correct(query: str, candidates: list[dict], llm) -> list[dict]:
    """
    CRAG grader: score each candidate snippet for relevance to query.
    If fewer than 2 are relevant, reformulate query and re-search once.
    Returns final list of relevant candidates (falls back to original if still poor).
    """
    if not candidates:
        return candidates

    snippets_text = "\n\n".join(
        f"[{i+1}] {c['name']}: {c['snippet'][:300]}"
        for i, c in enumerate(candidates)
    )

    grade_prompt = f"""You are a strict relevance grader for academic lab search results.

Student query: "{query}"

For each candidate, first identify their PRIMARY research domain (one phrase), then judge if it directly matches the query topic.
A candidate is relevant ONLY if their main research domain is the same as the query topic — not just because they use a related technique or have one tangential project.

For each candidate output exactly one line:
[N] relevant | primary domain: X | reason
or
[N] not_relevant | primary domain: X | reason

Candidates:
{snippets_text}

Output only the grading lines, nothing else."""

    response = llm.invoke(grade_prompt)
    content = response.content if hasattr(response, "content") else str(response)

    relevant = []
    for i, candidate in enumerate(candidates):
        marker = f"[{i+1}] relevant"
        if marker in content.lower():
            relevant.append(candidate)

    print(f"  [CRAG] {len(relevant)}/{len(candidates)} candidates relevant for query: '{query}'")

    if len(relevant) >= 2:
        return relevant

    # Quality too low — reformulate query and re-search
    rewrite_prompt = f"""The query "{query}" returned poor search results for finding robotics professors.
Rewrite it using more specific academic terminology that better matches how researchers describe their work.
Output only the rewritten query, nothing else."""

    rewrite_response = llm.invoke(rewrite_prompt)
    new_query = rewrite_response.content.strip().strip('"')
    print(f"  [CRAG] Reformulated query: '{new_query}'")

    new_candidates = _mmr_search(new_query)
    if not new_candidates:
        return candidates  # fallback to original

    # Re-grade new candidates
    new_snippets = "\n\n".join(
        f"[{i+1}] {c['name']}: {c['snippet'][:300]}"
        for i, c in enumerate(new_candidates)
    )
    regrade_prompt = f"""Query: "{new_query}"

{new_snippets}

For each, output:
[N] relevant | reason
or
[N] not_relevant | reason"""

    regrade_response = llm.invoke(regrade_prompt)
    regrade_content = regrade_response.content if hasattr(regrade_response, "content") else str(regrade_response)

    re_relevant = []
    for i, candidate in enumerate(new_candidates):
        marker = f"[{i+1}] relevant"
        if marker in regrade_content.lower():
            re_relevant.append(candidate)

    print(f"  [CRAG] After reformulation: {len(re_relevant)}/{len(new_candidates)} relevant")
    # only use reformulated results if they're strictly better
    if len(re_relevant) > len(relevant):
        return re_relevant
    return candidates  # fallback to original if reformulation didn't help


def _make_search_tool():
    called = False

    @tool
    def search_by_direction(query: str) -> str:
        """Search for professors by research direction or topic.
        Use this to find professors whose research matches a student's interests.
        Returns professor names and research summaries."""
        nonlocal called
        if called:
            return "Search already performed. Use the results from the previous search to make your recommendation."
        called = True

        llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
        candidates = _multi_query_search(query, llm)

        if not candidates:
            return "No results found."

        results = [
            f"Professor: {c['name']} ({c['dept']})\n{c['snippet']}"
            for c in candidates
        ]
        return "\n\n---\n\n".join(results)

    return search_by_direction


@tool
def get_professor_details(name: str) -> str:
    """Get complete information about a specific professor: their research focus,
    whether they recruit undergraduates, and how to join their lab.
    Use this after identifying promising candidates from search_by_direction."""
    data = get_professors_data()

    name_lower = name.lower().strip()
    professor = None
    for p in data:
        p_name_lower = p["name"].lower()
        if name_lower in p_name_lower or p_name_lower in name_lower:
            professor = p
            break

    if not professor:
        # Try matching by last name only
        last_name = name_lower.split()[-1]
        for p in data:
            if last_name in p["name"].lower():
                professor = p
                break

    if not professor:
        return f"Professor '{name}' not found. Available professors: {', '.join(p['name'] for p in data[:10])}..."

    pages = professor.get("scraped_pages", [])
    if not pages:
        return f"{professor['name']}: No detailed page content available (only index data)."

    PRIORITY_TYPES = {"research", "join", "people"}
    priority_pages = [p for p in pages if p.get("page_type") in PRIORITY_TYPES]
    selected_pages = priority_pages if priority_pages else pages[:2]

    sections = [f"# {professor['name']} ({professor.get('department', 'Robotics')})\n"]
    for page in selected_pages:
        page_type = page.get("page_type", "unknown")
        title = page.get("title", page_type)
        content = page.get("content", "")
        sections.append(f"## [{page_type.upper()}] {title}\n{content}")

    return "\n\n".join(sections)


def build_agent():
    load_environment()
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3)
    tools = [_make_search_tool(), get_professor_details]
    return create_react_agent(llm, tools, prompt=SystemMessage(content=SYSTEM_PROMPT))


def get_recommendations(student_input: str) -> str:
    agent = build_agent()

    result = agent.invoke(
        {"messages": [("user", student_input)]},
        config={"recursion_limit": 25}
    )
    content = result["messages"][-1].content

    # Gemini returns content as a list of blocks: [{type, text, extras}, ...]
    if isinstance(content, list):
        return "\n".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return content


def trace_recommendations(student_input: str):
    """Debug mode: prints full agent reasoning trace."""
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

    agent = build_agent()

    result = agent.invoke(
        {"messages": [("user", student_input)]},
        config={"recursion_limit": 25}
    )

    msgs = result["messages"]
    print(f"Total messages: {len(msgs)}\n")

    for i, msg in enumerate(msgs):
        if isinstance(msg, HumanMessage):
            print(f"[0] STUDENT: {msg.content}\n")

        elif isinstance(msg, AIMessage):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"[{i}] LLM → {tc['name']}({tc['args']})")
            else:
                content = msg.content
                if isinstance(content, list):
                    content = "\n".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                print(f"[{i}] FINAL ANSWER:\n{content}")

        elif isinstance(msg, ToolMessage):
            preview = msg.content[:300].replace("\n", " ")
            print(f"[{i}] {msg.name} returned: {preview}...\n")


if __name__ == "__main__":
    import sys
    load_environment()

    query = sys.argv[1] if len(sys.argv) > 1 else \
        "I'm a freshman interested in HRI, Python skills, no research experience."

    trace_recommendations(query)
