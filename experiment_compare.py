"""
Model comparison experiment.
Metrics: wall-clock time, disconnect, tool call count, EVAL lines, final answer.
Usage: python experiment_compare.py "your prompt here"
"""

import sys
import time
import os
import toml

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from backend import search_by_direction, get_professor_details, SYSTEM_PROMPT, load_environment

MODELS = [
    "gemini-flash-latest",
    "gemini-2.5-flash",
]

DIVIDER = "=" * 70


def build_fresh_agent(model_name: str):
    llm = ChatGoogleGenerativeAI(model=model_name, temperature=0.3)
    return create_react_agent(llm, [search_by_direction, get_professor_details],
                              prompt=SystemMessage(content=SYSTEM_PROMPT))


def run_one(model_name: str, prompt: str) -> dict:
    """Run agent with one model, return collected metrics."""
    print(f"\n{DIVIDER}")
    print(f"MODEL: {model_name}")
    print(DIVIDER)

    agent = build_fresh_agent(model_name)
    start = time.time()
    disconnected = False
    result = None

    try:
        result = agent.invoke(
            {"messages": [("user", prompt)]},
            config={"recursion_limit": 15}
        )
    except Exception as e:
        disconnected = True
        elapsed = time.time() - start
        print(f"[ERROR] {type(e).__name__}: {e}")
        return {
            "model": model_name,
            "elapsed": elapsed,
            "disconnected": True,
            "tool_calls": 0,
            "eval_lines": [],
            "final_answer": None,
        }

    elapsed = time.time() - start
    msgs = result["messages"]

    tool_call_count = 0
    eval_lines = []
    final_answer = None

    for i, msg in enumerate(msgs):
        if isinstance(msg, AIMessage):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_call_count += 1
                    print(f"  [tool call {tool_call_count}] {tc['name']}({tc['args']})")
            else:
                content = msg.content
                if isinstance(content, list):
                    content = "\n".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                # Extract EVAL lines
                for line in content.splitlines():
                    if line.strip().startswith("EVAL:"):
                        eval_lines.append(line.strip())
                        print(f"  {line.strip()}")
                if not (hasattr(msg, "tool_calls") and msg.tool_calls):
                    final_answer = content

        elif isinstance(msg, ToolMessage):
            preview = msg.content[:150].replace("\n", " ")
            print(f"  [tool result] {msg.name}: {preview}...")

    print(f"\n  Total tool calls : {tool_call_count}")
    print(f"  EVAL lines found : {len(eval_lines)}")
    print(f"  Elapsed          : {elapsed:.1f}s")
    print(f"  Disconnected     : {disconnected}")
    if final_answer:
        print(f"\n--- FINAL ANSWER ---\n{final_answer[:1200]}")

    return {
        "model": model_name,
        "elapsed": elapsed,
        "disconnected": disconnected,
        "tool_calls": tool_call_count,
        "eval_lines": eval_lines,
        "final_answer": final_answer,
    }


def print_summary(results: list[dict]):
    print(f"\n\n{'=' * 70}")
    print("COMPARISON SUMMARY")
    print('=' * 70)
    print(f"{'Model':<30} {'Time':>7}  {'Disconnect':>10}  {'Tool calls':>10}  {'EVALs':>6}")
    print("-" * 70)
    for r in results:
        print(
            f"{r['model']:<30} {r['elapsed']:>6.1f}s  "
            f"{'YES' if r['disconnected'] else 'no':>10}  "
            f"{r['tool_calls']:>10}  "
            f"{len(r['eval_lines']):>6}"
        )

    print("\nEVAL lines per model:")
    for r in results:
        print(f"\n  [{r['model']}]")
        if r["eval_lines"]:
            for line in r["eval_lines"]:
                print(f"    {line}")
        else:
            print("    (none)")


if __name__ == "__main__":
    load_environment()

    prompt = sys.argv[1] if len(sys.argv) > 1 else \
        "I'm a freshman interested in HRI and human-robot collaboration. I know Python. Which labs should I contact?"

    print(f"PROMPT: {prompt}\n")

    results = []
    for model in MODELS:
        r = run_one(model, prompt)
        results.append(r)

    print_summary(results)
