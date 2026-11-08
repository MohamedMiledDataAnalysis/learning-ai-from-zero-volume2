"""Chapter 5: logs, traces, golden files and the design of the 40-question evaluation.

Run from the repository root:
    python python/vol2/ch05/tracing.py trace       a run written as a trace (one JSON line per step)
    python python/vol2/ch05/tracing.py golden      compare today's note with the golden file
    python python/vol2/ch05/tracing.py diff        what a golden-file failure looks like
    python python/vol2/ch05/tracing.py design      how the 40 questions are spread
    python python/vol2/ch05/tracing.py make-golden (re)write the golden file — only after a reviewed change
"""
import difflib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "python"))
from tar_agent.agent import ask  # noqa: E402
from tar_agent.tools.note import draft_surveillance_note  # noqa: E402

GOLDEN = HERE / "golden" / "note_2026_10.md"


def trace_records(question):
    """Run the agent and turn its steps into trace records (no timings: they differ on every computer)."""
    out = ask(question, mode="rules", log=lambda m: None)
    records = []
    for s in out["steps"]:
        rec = {"step": s["step"], "type": s["type"]}
        if s["type"] == "tool":
            rec.update(tool=s["name"], arguments=s["arguments"], result_chars=len(s["result"]),
                       error="error" in json.loads(s["result"]))
        records.append(rec)
    records.append({"step": "end", "stopped_because": out["stopped_because"], "answer": out["answer"]})
    return records


def trace():
    for rec in trace_records("Run the trigger tests for period 10."):
        print(json.dumps(rec))


def make_golden():
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(draft_surveillance_note(10)["note_markdown"] + "\n", encoding="utf-8")
    print(f"Golden file written: {GOLDEN.relative_to(ROOT)}")


def golden():
    today = draft_surveillance_note(10)["note_markdown"] + "\n"
    expected = GOLDEN.read_text(encoding="utf-8")
    print("Golden file check:", "identical" if today == expected else "DIFFERENT")


def diff():
    """Compare the period 11 note with the period 10 golden file, as if period 10 had changed."""
    changed = draft_surveillance_note(11)["note_markdown"].replace("period 11", "period 10") + "\n"
    expected = GOLDEN.read_text(encoding="utf-8")
    lines = list(difflib.unified_diff(expected.splitlines(), changed.splitlines(),
                                      fromfile="golden/note_2026_10.md", tofile="today", lineterm="", n=0))
    print(f"Golden file check: DIFFERENT ({sum(1 for x in lines if x.startswith('-') and not x.startswith('---'))} lines changed)")
    for line in lines[:13]:   # whole hunks only: the first three changes
        print(line)


def design():
    qs = [json.loads(x) for x in (ROOT / "data" / "eval" / "questions.jsonl").read_text().splitlines() if x]
    print(f"Questions: {len(qs)}")
    by_tool = Counter(q["tools"][0] for q in qs)
    for tool, n in sorted(by_tool.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {tool:<26}{n:>3}")
    kinds = Counter(q["expected"]["kind"] for q in qs)
    print(f"Expected answers: {kinds['number']} numbers, {kinds['text']} texts; "
          f"{sum(1 for q in qs if 'page' in q['expected'])} must cite a page")


if __name__ == "__main__":
    {"trace": trace, "golden": golden, "diff": diff, "design": design,
     "make-golden": make_golden}[sys.argv[1] if len(sys.argv) > 1 else "trace"]()
