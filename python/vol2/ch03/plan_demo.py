"""Chapter 3: plans, checked against a checklist, then run.

Run from the repository root:
    python python/vol2/ch03/plan_demo.py plan        the plan written by rules for period 10
    python python/vol2/ch03/plan_demo.py check       an incomplete plan, completed by the checklist
    python python/vol2/ch03/plan_demo.py cycle       two monthly cycles (periods 9 and 10) with memory
    python python/vol2/ch03/plan_demo.py replan      a plan for the wrong period, rejected, then replanned once
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent_core.brains import RuleBrain  # noqa: E402
from tar_agent.agentic import check_plan, rule_plan, run_surveillance  # noqa: E402


def show(plan):
    for i, step in enumerate(plan, start=1):
        print(f"{i}. {step['tool']}({json.dumps(step.get('arguments', {}))})")
        print(f"   why: {step['why']}")


def plan():
    show(rule_plan(10))


def check():
    # A plan written by hand for this demonstration: it forgets the regional stratifications,
    # and one step asks for period 9 although the goal is period 10.
    incomplete = [
        {"tool": "run_trigger_tests", "arguments": {"period": 10}, "why": "check the triggers"},
        {"tool": "stratify_pool", "arguments": {"by": "region", "measure": "balance_90plus", "period": 9},
         "why": "regional arrears"},
        {"tool": "draft_surveillance_note", "arguments": {"period": 10}, "why": "write the note"},
    ]
    completed, missing, rejected = check_plan(incomplete, 10)
    print(f"Steps in the plan received: {len(incomplete)}")
    print(f"Steps rejected:             {len(rejected)}")
    for r in rejected:
        print(f"  - {r['reason']}")
    print(f"Checklist items missing:    {len(missing)}")
    print()
    show(completed)


def cycle():
    with tempfile.TemporaryDirectory() as tmp:
        memory, out = Path(tmp) / "memory", Path(tmp) / "out"
        for period, approve in ((9, True), (10, False)):
            result = run_surveillance(period, memory_dir=memory, out_dir=out, approve=approve)
            print("Month on month:")
            for line in result["changes"]:
                print(f"  {line}")
            print()
        saved = json.loads((memory / "surveillance_memory.json").read_text())
        print("Memory file now holds periods:", ", ".join(sorted(saved, key=int)))


def replan():
    # A stand-in for a model: its first plan is entirely for period 9, its second is right.
    wrong = [{**s, "arguments": {**s["arguments"], "period": 9}} for s in rule_plan(10)]
    replies = iter([json.dumps(wrong), json.dumps(rule_plan(10))])
    brain = RuleBrain(lambda memory: {"content": next(replies), "tool_calls": []})
    with tempfile.TemporaryDirectory() as tmp:
        result = run_surveillance(10, plan_source="model", brain=brain, memory_dir=Path(tmp) / "m",
                                  out_dir=Path(tmp) / "o", approve=False)
    print("Replanned:", result["replanned"], "| status:", result["status"])


if __name__ == "__main__":
    {"plan": plan, "check": check, "cycle": cycle, "replan": replan}[sys.argv[1] if len(sys.argv) > 1 else "plan"]()
