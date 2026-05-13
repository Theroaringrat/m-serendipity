import os
from typing import List

import streamlit as st
import toml
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import BaseModel

DB_DIR = "vector_db"


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


class ProfessorMatch(BaseModel):
    alignment_score: int
    rationale: str
    serendipity_note: str


class RecommendationOutput(BaseModel):
    matches: List[ProfessorMatch]


def get_recommendations(student_input: str):
    load_environment()

    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    vectorstore = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)

    raw_docs = vectorstore.similarity_search(student_input, k=12)

    seen_names = set()
    docs = []
    for doc in raw_docs:
        name = doc.metadata.get("name")
        if name not in seen_names:
            seen_names.add(name)
            docs.append(doc)
        if len(docs) >= 6:
            break

    llm = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0.7)

    candidates_text = ""
    for i, doc in enumerate(docs):
        candidates_text += (
            f"\n--- CANDIDATE {i+1} ---\n"
            f"Name: {doc.metadata.get('name')}\n"
            f"Dept: {doc.metadata.get('department')}\n"
            f"Page Type: {doc.metadata.get('page_type', 'unknown')} "
            f"(research=方向, people=成员/本科生, join=招募, home=概述, teaching=课程)\n"
            f"Source: {doc.metadata.get('page_title')}\n"
            f"Context: {doc.page_content}\n"
        )

    n_candidates = len(docs)
    prompt_template = """
    You are a wise academic mentor. Analyze the synergy between a student's interest and the following {n_candidates} candidate professors.

    Student Interest: '{student_input}'

    Candidates:
    {candidates_text}

    SCORING RUBRIC:
    - SKEPTICAL DEFAULT: Assume the interest is TANGENTIAL (Low Score) unless proven otherwise.
    - HIGH SCORE (8-10): The interest is a CENTRAL THEME in Research Interests or Project Titles.
    - MEDIUM SCORE (5-7): Valid connection but secondary.
    - LOW SCORE (1-4): The keyword appears ONLY in news, alumni, or publication lists.

    You MUST provide exactly {n_candidates} entries in the matches array — one per candidate, in order.
    For each candidate, provide an alignment_score (1-10), a specific rationale (2 sentences), and an inspiring serendipity_note (1 sentence).
    """

    prompt = PromptTemplate(
        input_variables=["student_input", "candidates_text", "n_candidates"],
        template=prompt_template,
    )

    structured_llm = llm.with_structured_output(RecommendationOutput)
    chain = prompt | structured_llm

    try:
        output = chain.invoke({
            "student_input": student_input,
            "candidates_text": candidates_text,
            "n_candidates": n_candidates,
        })
    except Exception as e:
        return [
            {
                "name": doc.metadata.get("name"),
                "department": doc.metadata.get("department"),
                "alignment_score": 0,
                "rationale": f"Error: {e}",
                "note": "Service unavailable.",
                "source_url": doc.metadata.get("source_url", "#"),
                "page_title": doc.metadata.get("page_title", "Profile"),
                "research_interests": doc.page_content,
            }
            for doc in docs
        ]

    results = []
    for i, doc in enumerate(docs):
        match = output.matches[i] if i < len(output.matches) else None
        results.append({
            "name": doc.metadata.get("name"),
            "department": doc.metadata.get("department"),
            "alignment_score": match.alignment_score if match else 5,
            "rationale": match.rationale if match else "Analysis unavailable.",
            "note": match.serendipity_note if match else "Connection found.",
            "source_url": doc.metadata.get("source_url", "#"),
            "page_title": doc.metadata.get("page_title", "Profile"),
            "research_interests": doc.page_content,
        })

    return results


if __name__ == "__main__":
    test_input = "I am interested in how machines perceive time and memory."
    recs = get_recommendations(test_input)
    for rec in recs:
        print(f"--- {rec['name']} ---")
        print(f"Score: {rec['alignment_score']}/10")
        print(f"Rationale: {rec['rationale']}")
        print(f"Note: {rec['note']}")
        print()
