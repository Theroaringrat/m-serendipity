"""
Stress test for gemini-flash-latest.
Tests: timeout behavior, recommendation correctness, consistency, multi-step tool calls.
Usage: python experiment_stress.py
"""

import sys
import time
import traceback

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from backend import search_by_direction, get_professor_details, SYSTEM_PROMPT, load_environment

MODEL = "gemini-flash-latest"

PROMPTS = [
    # (id, label, prompt)
    ("P1", "HRI freshman",
     "I'm a freshman interested in HRI and human-robot collaboration. I know Python. Which labs should I contact?"),
    ("P2", "CV & manipulation",
     "I have computer vision and manipulation experience, looking for a robotics lab."),
    ("P3", "Autonomous vehicles",
     "I'm interested in autonomous driving and motion planning. What labs work on this?"),
    ("P4", "ML + undergrad",
     "I want a lab that does machine learning applied to robotics and actively recruits undergraduates."),
    ("P5", "HRI freshman (repeat)",
     "I'm a freshman interested in HRI and human-robot collaboration. I know Python. Which labs should I contact?"),
]


def extract_content(msg_content):
    if isinstance(msg_content, list):
        return "\n".join(
            b.get("text", "") for b in msg_content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return msg_content or ""


def run_one(run_id: str, label: str, prompt: str) -> dict:
    print(f"\n{'=' * 70}")
    print(f"[{run_id}] {label}")
    print(f"Prompt: {prompt}")
    print('=' * 70)

    llm = ChatGoogleGenerativeAI(model=MODEL, temperature=0.3, thinking_budget=2048)
    agent = create_react_agent(
        llm, [search_by_direction, get_professor_details],
        prompt=SystemMessage(content=SYSTEM_PROMPT)
    )

    start = time.time()
    error_type = None
    result = None

    try:
        result = agent.invoke(
            {"messages": [("user", prompt)]},
            config={"recursion_limit": 15}
        )
    except Exception as e:
        error_type = type(e).__name__
        elapsed = time.time() - start
        print(f"  [TIMEOUT/ERROR] {error_type}: {str(e)[:200]}")
        return {
            "id": run_id, "label": label,
            "elapsed": round(elapsed, 1),
            "error": error_type,
            "tool_calls": 0,
            "tools_sequence": [],
            "eval_lines": [],
            "recommended": [],
            "final_answer": None,
        }

    elapsed = time.time() - start
    msgs = result["messages"]

    tool_calls = 0
    tools_sequence = []
    eval_lines = []
    recommended = []
    final_answer = None

    for msg in msgs:
        if isinstance(msg, AIMessage):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls += 1
                    tools_sequence.append(f"{tc['name']}({list(tc['args'].values())[0][:40]})")
                    print(f"  [call {tool_calls}] {tc['name']}({list(tc['args'].values())[0][:60]})")
            else:
                content = extract_content(msg.content)
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("EVAL:"):
                        eval_lines.append(stripped)
                        print(f"  {stripped}")
                if content.strip():
                    final_answer = content

    # Extract recommended professor names from EVAL lines
    for line in eval_lines:
        try:
            name = line.split("|")[0].replace("EVAL:", "").strip()
            verdict = [p for p in line.split("|") if "keep" in p.lower() or "reject" in p.lower()]
            verdict_str = verdict[0].strip() if verdict else "?"
            recommended.append(f"{name} ({verdict_str})")
        except Exception:
            pass

    print(f"\n  Tool calls   : {tool_calls}")
    print(f"  Sequence     : {' → '.join(tools_sequence)}")
    print(f"  EVAL lines   : {len(eval_lines)}")
    print(f"  Elapsed      : {elapsed:.1f}s")
    print(f"  Error        : {error_type or 'none'}")
    if final_answer:
        print(f"\n  [Final answer preview]\n  {final_answer[:600].replace(chr(10), chr(10)+'  ')}")

    return {
        "id": run_id, "label": label,
        "elapsed": round(elapsed, 1),
        "error": error_type or "none",
        "tool_calls": tool_calls,
        "tools_sequence": tools_sequence,
        "eval_lines": eval_lines,
        "recommended": recommended,
        "final_answer": final_answer,
    }


def print_summary(results: list[dict]):
    print(f"\n\n{'=' * 90}")
    print(f"STRESS TEST SUMMARY  —  model: {MODEL}")
    print('=' * 90)

    # Main table
    print(f"\n{'ID':<4} {'Label':<25} {'Time':>6}  {'Error':<22} {'Calls':>5}  {'EVALs':>5}")
    print("-" * 75)
    for r in results:
        print(
            f"{r['id']:<4} {r['label']:<25} {r['elapsed']:>5.1f}s  "
            f"{str(r['error']):<22} {r['tool_calls']:>5}  {len(r['eval_lines']):>5}"
        )

    # Recommendations table
    print(f"\n\n{'ID':<4} {'Label':<25}  Recommended (keep/reject)")
    print("-" * 90)
    for r in results:
        recs = " | ".join(r["recommended"]) if r["recommended"] else "(none / error)"
        print(f"{r['id']:<4} {r['label']:<25}  {recs}")

    # Tool call sequences
    print(f"\n\n{'ID':<4} {'Label':<25}  Tool call sequence")
    print("-" * 90)
    for r in results:
        seq = " → ".join(r["tools_sequence"]) if r["tools_sequence"] else "(no calls)"
        print(f"{r['id']:<4} {r['label']:<25}  {seq[:90]}")

    # Consistency check (P1 vs P5)
    p1 = next((r for r in results if r["id"] == "P1"), None)
    p5 = next((r for r in results if r["id"] == "P5"), None)
    if p1 and p5:
        print(f"\n\n--- CONSISTENCY CHECK (P1 vs P5, same prompt) ---")
        p1_names = set(e.split("|")[0].replace("EVAL:", "").strip() for e in p1["eval_lines"])
        p5_names = set(e.split("|")[0].replace("EVAL:", "").strip() for e in p5["eval_lines"])
        overlap = p1_names & p5_names
        print(f"  P1 recommended : {p1_names}")
        print(f"  P5 recommended : {p5_names}")
        print(f"  Overlap        : {overlap}")
        print(f"  Consistent     : {'YES' if p1_names == p5_names else 'PARTIAL' if overlap else 'NO'}")

    # EVAL detail
    print(f"\n\n--- EVAL LINES DETAIL ---")
    for r in results:
        print(f"\n  [{r['id']}] {r['label']}")
        if r["eval_lines"]:
            for line in r["eval_lines"]:
                print(f"    {line}")
        else:
            print("    (none)")


if __name__ == "__main__":
    load_environment()

    results = []
    for run_id, label, prompt in PROMPTS:
        r = run_one(run_id, label, prompt)
        results.append(r)
        time.sleep(2)  # brief pause between runs

    print_summary(results)
