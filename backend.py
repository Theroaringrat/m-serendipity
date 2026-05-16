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
2. Call get_professor_details for at most 3 of the top candidates
3. Write your final answer immediately after — do not search again

For each of the 3 recommended professors, explain:
- Why their research matches the student's interests
- Whether they recruit undergraduate researchers (based on their join/people pages)
- Why this lab is worth contacting

Be concise and grounded. Do not repeat tool calls."""


def load_environment():
    if "GOOGLE_API_KEY" not in os.environ:
        try:
            os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            try:
                secrets = toml.load(".streamlit/secrets.toml")
                os.environ["GOOGLE_API_KEY"] = secrets["GOOGLE_API_KEY"]
            except Exception:
                print("Warning: GOOGLE_API_KEY not found.")


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


@tool
def search_by_direction(query: str) -> str:
    """Search for professors by research direction or topic.
    Use this to find professors whose research matches a student's interests.
    Returns professor names and research summaries."""
    vectorstore = get_vectorstore()
    docs = vectorstore.similarity_search(
        query, k=6,
        filter={"page_type": {"$in": ["research", "home"]}}
    )

    if not docs:
        return "No results found."

    seen = set()
    results = []
    for doc in docs:
        name = doc.metadata.get("name", "Unknown")
        if name in seen:
            continue
        seen.add(name)
        dept = doc.metadata.get("department", "")
        snippet = doc.page_content[:500]
        results.append(f"Professor: {name} ({dept})\n{snippet}")

    return "\n\n---\n\n".join(results)


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

    sections = [f"# {professor['name']} ({professor.get('department', 'Robotics')})\n"]
    for page in pages:
        page_type = page.get("page_type", "unknown")
        title = page.get("title", page_type)
        content = page.get("content", "")[:3000]
        sections.append(f"## [{page_type.upper()}] {title}\n{content}")

    return "\n\n".join(sections)


_agent = None


def build_agent():
    load_environment()
    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.3)
    tools = [search_by_direction, get_professor_details]
    return create_react_agent(llm, tools, prompt=SystemMessage(content=SYSTEM_PROMPT))


def get_recommendations(student_input: str) -> str:
    global _agent
    if _agent is None:
        _agent = build_agent()

    result = _agent.invoke(
        {"messages": [("user", student_input)]},
        config={"recursion_limit": 15}
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

    global _agent
    if _agent is None:
        _agent = build_agent()

    result = _agent.invoke(
        {"messages": [("user", student_input)]},
        config={"recursion_limit": 15}
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
