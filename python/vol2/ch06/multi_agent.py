"""Chapter 6: three agents in a pipeline — checker, analyst, reviewer — coordinated by an orchestrator.

Each agent is the same loop as before, with its own instructions, its own allowed tools,
and its own rule brain. The orchestrator passes each agent's output to the next one.

Run from the repository root:
    python python/vol2/ch06/multi_agent.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent_core.brains import RuleBrain  # noqa: E402
from agent_core.loop import run_agent  # noqa: E402
from tar_agent.registry import call_tool, tool_schemas  # noqa: E402

PERIOD = 10


def tools_for(names):
    """Schemas and a call function limited to some tools: each agent sees only what it needs."""
    schemas = [s for s in tool_schemas() if s["function"]["name"] in names]

    def call(name, args):
        if name not in names:
            return json.dumps({"error": f"tool {name} not available to this agent"})
        return call_tool(name, args)
    return schemas, call


def one_call_then(tool, args, answer):
    """A rule brain: call one tool, then answer with a function of its result."""
    def rules(memory):
        if memory[-1]["role"] != "tool":
            return {"content": "", "tool_calls": [{"name": tool, "arguments": args}]}
        return {"content": answer(json.loads(memory[-1]["content"])), "tool_calls": []}
    return RuleBrain(rules)


def checker():
    def answer(r):
        ok = all(t["agrees_with_report"] for t in r["tests"])
        return "DATA OK: recomputed ratios agree with the investor report." if ok else \
               "DATA PROBLEM: recomputed ratios differ from the investor report."
    schemas, call = tools_for({"run_trigger_tests"})
    return run_agent(f"Check the data for period {PERIOD}.", one_call_then("run_trigger_tests", {"period": PERIOD},
                     answer), schemas, call, "You check data quality only.", log=lambda m: None)["answer"]


def analyst(checker_report):
    if not checker_report.startswith("DATA OK"):
        return None
    schemas, call = tools_for({"draft_surveillance_note"})
    return run_agent(f"Draft the note for period {PERIOD}.", one_call_then(
        "draft_surveillance_note", {"period": PERIOD}, lambda r: r["note_markdown"]),
        schemas, call, "You draft surveillance notes.", log=lambda m: None)["answer"]


def reviewer(note):
    """Recompute the 90+ ratio and check that the note quotes it."""
    def answer(r):
        a90 = next(t for t in r["tests"] if t["test"] == "arrears_90_ratio")
        quoted = re.search(r"90\+ day arrears ratio: (\d+\.\d+)%", note)
        ok = quoted and abs(float(quoted.group(1)) / 100 - a90["value"]) < 0.00005
        return f"APPROVED: note quotes {quoted.group(1)}%, tool gives {a90['value']:.2%}." if ok else \
               "REJECTED: the note's 90+ ratio does not match the trigger tool."
    schemas, call = tools_for({"run_trigger_tests"})
    return run_agent("Review the note.", one_call_then("run_trigger_tests", {"period": PERIOD}, answer),
                     schemas, call, "You review notes; you do not write them.", log=lambda m: None)["answer"]


if __name__ == "__main__":
    report = checker()
    print("Checker  ->", report)
    note = analyst(report)
    print("Analyst  ->", note.splitlines()[0], f"({len(note.splitlines())} lines)")
    print("Reviewer ->", reviewer(note))
    tampered = note.replace("1.32%", "1.12%")
    print("Reviewer (tampered note) ->", reviewer(tampered))
