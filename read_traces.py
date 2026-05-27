"""
Read recent LangSmith traces from m-serendipity project.
Usage:
  python read_traces.py           — list last 10 runs
  python read_traces.py <run_id>  — print flat trace for that run
"""

import sys
import os
import toml
from langsmith import Client
from datetime import datetime, timezone

secrets = toml.load(".streamlit/secrets.toml")
os.environ["LANGSMITH_API_KEY"] = secrets["LANGSMITH_API_KEY"]
PROJECT = secrets.get("LANGSMITH_PROJECT", "m-serendipity")

client = Client()


def fmt_time(dt):
    return dt.strftime("%H:%M:%S") if dt else "?"


def fmt_dur(run):
    if run.end_time and run.start_time:
        return f"{(run.end_time - run.start_time).total_seconds():.1f}s"
    return "?"


def list_runs(n=10):
    runs = list(client.list_runs(
        project_name=PROJECT,
        run_type="chain",
        is_root=True,
        limit=n,
    ))
    print(f"\nLast {len(runs)} runs in [{PROJECT}]:\n")
    print(f"{'#':<3} {'Run ID':<38} {'Time':>8}  {'Dur':>6}  {'Status'}  Input")
    print("-" * 95)
    for i, r in enumerate(runs):
        preview = ""
        msgs = (r.inputs or {}).get("messages", [])
        if msgs:
            last = msgs[-1]
            if isinstance(last, (list, tuple)) and len(last) >= 2:
                preview = str(last[1])[:65]
            elif isinstance(last, dict):
                preview = str(last.get("content", ""))[:65]
        status = "✅" if not r.error else "❌"
        print(f"{i+1:<3} {str(r.id):<38} {fmt_time(r.start_time):>8}  {fmt_dur(r):>6}  {status}  {preview}")
    print()
    return runs


def show_run(run_id: str):
    # Fetch all runs in this trace at once (flat list)
    all_runs = list(client.list_runs(
        project_name=PROJECT,
        trace_id=run_id,
        limit=100,
    ))

    # Sort by start time
    all_runs.sort(key=lambda r: r.start_time or datetime.min.replace(tzinfo=timezone.utc))

    root = next((r for r in all_runs if str(r.id) == run_id), None)
    print(f"\n{'='*80}")
    print(f"Trace: {run_id}")
    if root:
        print(f"Total duration: {fmt_dur(root)}  |  Steps: {len(all_runs)}")
    print(f"{'='*80}\n")

    for r in all_runs:
        depth = 0
        pid = r.parent_run_id
        while pid:
            parent = next((x for x in all_runs if x.id == pid), None)
            if parent:
                depth += 1
                pid = parent.parent_run_id
            else:
                break

        prefix = "  " * depth
        rtype = (r.run_type or "?").upper()
        name = r.name or rtype
        dur = fmt_dur(r)
        err = f"  ❌ {r.error[:100]}" if r.error else ""

        # Input
        inp = ""
        if r.run_type == "tool" and r.inputs:
            vals = list(r.inputs.values())
            inp = f"  IN: {str(vals[0])[:100]}" if vals else ""
        elif r.run_type == "llm" and r.inputs:
            msgs = r.inputs.get("messages", [])
            if msgs:
                last = msgs[-1] if isinstance(msgs[-1], dict) else {}
                content = last.get("content", "")
                if isinstance(content, list):
                    content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                inp = f"  IN: {str(content)[:100]}"

        # Output
        out = ""
        if r.run_type == "tool" and r.outputs and not r.error:
            vals = list(r.outputs.values())
            out = f"  OUT: {str(vals[0])[:150]}" if vals else ""
        elif r.run_type == "llm" and r.outputs and not r.error:
            gens = r.outputs.get("generations", [[]])
            if gens and gens[0]:
                text = gens[0][0].get("text", "") or str(gens[0][0].get("message", {}).get("content", ""))
                if isinstance(text, list):
                    text = " ".join(b.get("text", "") for b in text if isinstance(b, dict))
                out = f"  OUT: {str(text)[:150]}"

        print(f"{prefix}[{rtype}] {name}  ({dur}){err}")
        if inp:
            print(f"{prefix}{inp}")
        if out:
            print(f"{prefix}{out}")
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show_run(sys.argv[1])
    else:
        runs = list_runs(10)
        print("→ python read_traces.py <run_id>  to see full trace")
