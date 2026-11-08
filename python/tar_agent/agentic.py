"""From agent to agentic system: monthly surveillance from a single goal.

Goal: "Keep Thames Auto Receivables 2026-1 under surveillance."
Each month the system:
  1. PLANS the checks (rules or a model writes the plan),
  2. CHECKS the plan: removes steps for another period or an unknown tool, adds any missing checklist step,
  3. RUNS the plan with the five tools, and REPLANS once if the plan was unusable or a step failed,
  4. SELF-CHECKS one figure by recomputing it with a second tool (a failure holds the note),
  5. REMEMBERS the month's key figures and compares them with last month,
  6. ASKS A HUMAN before sending the note (the one action that cannot be undone).

    python -m tar_agent.agentic --period 10              asks "Send the note? (yes/no)"
    python -m tar_agent.agentic --period 10 --approve    sends without asking: nobody reads the note first
    python -m tar_agent.agentic --period 10 --no-approve keeps the note as a draft
"""

import argparse
import json
import re
import sys
from pathlib import Path

from .data import DATA_DIR, check_period
from .registry import TOOLS, call_tool

OUT = DATA_DIR.parent / "out"

# What an analyst checks every month. A plan missing any of these is completed before it runs.
CHECKLIST = [
    {"tool": "run_trigger_tests", "why": "check the trigger tests and the payment mode"},
    {"tool": "stratify_pool", "arguments": {"by": "region", "measure": "balance_90plus"},
     "why": "find where 90+ day arrears are concentrated"},
    {"tool": "stratify_pool", "arguments": {"by": "region", "measure": "balance"},
     "why": "pool balance by region, for the self-check"},
    {"tool": "draft_surveillance_note", "why": "draft the monthly note"},
]

PLAN_PROMPT = """You plan the monthly surveillance of a securitisation. Available tools:
validate_loan_tape, stratify_pool(by, period, measure), run_trigger_tests(period),
search_prospectus(query), draft_surveillance_note(period).
Reply with ONLY a JSON list of steps for period {period}, each step like
{{"tool": "...", "arguments": {{...}}, "why": "..."}}."""


# --------------------------------------------------------------------------
# 1-2. Plan, and check the plan
# --------------------------------------------------------------------------

def rule_plan(period):
    """The plan written by rules: the checklist itself, for this period."""
    return [{"tool": s["tool"], "arguments": {**s.get("arguments", {}), "period": period}, "why": s["why"]}
            for s in CHECKLIST]


def model_plan(brain, period, feedback=None):
    """Ask a model for the plan. Returns a list of steps, or [] if the reply is not a JSON list.
    feedback: the problems found in the previous plan, sent back when the system replans."""
    prompt = PLAN_PROMPT.format(period=period)
    if feedback:
        prompt += "\nYour previous plan had these problems:\n" + "\n".join(f"- {f}" for f in feedback)
    reply = brain.next([{"role": "user", "content": prompt}], [])
    match = re.search(r"\[.*\]", reply.get("content", ""), flags=re.S)
    try:
        steps = json.loads(match.group(0)) if match else []
    except json.JSONDecodeError:
        steps = []
    return [s for s in steps if isinstance(s, dict) and "tool" in s]


def matches(step, item, period):
    if step.get("tool") != item["tool"] or step.get("arguments", {}).get("period") != period:
        return False
    return all(step.get("arguments", {}).get(k) == v for k, v in item.get("arguments", {}).items())


def check_plan(plan, period):
    """Return (completed plan, missing checklist items, rejected steps with the reason).
    A step is rejected if its tool does not exist or it is for another period than the goal's."""
    kept, rejected = [], []
    for s in plan:
        if s.get("tool") not in TOOLS:
            rejected.append({"step": s, "reason": f"unknown tool '{s.get('tool')}'"})
        elif "period" in TOOLS[s["tool"]]["parameters"]["properties"] and \
                s.get("arguments", {}).get("period") != period:
            rejected.append({"step": s, "reason": f"{s['tool']} is for period "
                             f"{s.get('arguments', {}).get('period')}, not period {period}"})
        else:
            kept.append(s)
    missing = [item for item in CHECKLIST if not any(matches(s, item, period) for s in kept)]
    completed = kept + [{"tool": m["tool"], "arguments": {**m.get("arguments", {}), "period": period},
                         "why": m["why"] + " (added: missing from the plan)"} for m in missing]
    return completed, missing, rejected


# --------------------------------------------------------------------------
# 3-5. Run, self-check, remember
# --------------------------------------------------------------------------

def run_plan(plan, log):
    results = []
    for i, step in enumerate(plan, start=1):
        result = json.loads(call_tool(step["tool"], step.get("arguments", {})))
        log(f"  step {i}: {step['tool']}({json.dumps(step.get('arguments', {}))}) — {step['why']}")
        results.append({"step": step, "result": result})
    return results


def find(results, tool, **args):
    """The first successful result of this tool with these arguments (results with an error are skipped)."""
    for r in results:
        if r["step"]["tool"] == tool and "error" not in r["result"] and \
                all(r["step"].get("arguments", {}).get(k) == v for k, v in args.items()):
            return r["result"]
    return None


def errors(results):
    return [f"{r['step']['tool']}({json.dumps(r['step'].get('arguments', {}))}) failed: {r['result']['error']}"
            for r in results if "error" in r["result"]]


def self_check(results, period):
    """Recompute the 90+ day arrears ratio from two stratifications and compare it with the trigger tool."""
    arrears = find(results, "stratify_pool", measure="balance_90plus", period=period)
    balance = find(results, "stratify_pool", measure="balance", period=period)
    trig = find(results, "run_trigger_tests", period=period)
    if arrears is None or balance is None or trig is None:
        return {"figure": "90+ day arrears ratio", "agree": False,
                "error": "a result needed for the self-check is missing or failed"}
    value = next(t for t in trig["tests"] if t["test"] == "arrears_90_ratio")["value"]
    recomputed = arrears["total"] / balance["total"]
    return {"figure": "90+ day arrears ratio", "trigger_tool": value, "recomputed": round(recomputed, 6),
            "agree": abs(recomputed - value) < 1e-6}


def key_figures(results, period):
    trig = find(results, "run_trigger_tests", period=period)
    tests = {t["test"]: t["value"] for t in trig["tests"]}
    top = find(results, "stratify_pool", measure="balance_90plus", period=period)["rows"][0]
    return {"arrears_90_ratio": tests["arrears_90_ratio"], "cumulative_default_ratio": tests["cumulative_default_ratio"],
            "principal_payment_mode": trig["principal_payment_mode"], "main_arrears_region": top["group"]}


def load_memory(memory_dir):
    path = Path(memory_dir) / "surveillance_memory.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_memory(memory_dir, memory):
    path = Path(memory_dir) / "surveillance_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(memory, indent=2, sort_keys=True), encoding="utf-8")


def latest_before(memory, period):
    """The most recent month in memory before this period, as (period, figures), or (None, None)."""
    bad = [k for k in memory if not k.isdigit()]
    if bad:
        raise ValueError(f"memory key '{bad[0]}' is not a period number: keys must be like \"9\"")
    earlier = sorted(int(k) for k in memory if int(k) < period)
    return (earlier[-1], memory[str(earlier[-1])]) if earlier else (None, None)


def compare(previous, current, previous_period=None):
    if not previous:
        return ["No earlier month in memory: this is the first month monitored."]
    lines = []
    d = (current["arrears_90_ratio"] - previous["arrears_90_ratio"]) * 100
    since = "the previous month" if previous_period is None else f"period {previous_period}"
    lines.append(f"90+ day arrears ratio moved by {d:+.2f} points since {since} "
                 f"({previous['arrears_90_ratio'] * 100:.2f}% to {current['arrears_90_ratio'] * 100:.2f}%).")
    if previous["principal_payment_mode"] != current["principal_payment_mode"]:
        lines.append(f"Payment mode CHANGED from {previous['principal_payment_mode']} to "
                     f"{current['principal_payment_mode']}.")
    if previous["main_arrears_region"] != current["main_arrears_region"]:
        lines.append(f"Main arrears region changed from {previous['main_arrears_region']} to "
                     f"{current['main_arrears_region']}.")
    return lines


# --------------------------------------------------------------------------
# 6. The full cycle, with human approval
# --------------------------------------------------------------------------

def ask_human(note):
    print(note)
    return input("Send the note? (yes/no) ").strip().lower() in ("y", "yes")


def run_surveillance(period, plan_source="rules", brain=None, memory_dir=None, out_dir=None,
                     approve=None, log=print):
    """One monthly cycle. approve: True, False, or None to ask the human with input()."""
    check_period(period)
    memory_dir = Path(memory_dir or DATA_DIR / "memory")
    out_dir = Path(out_dir or OUT)
    log(f"Goal: keep the deal under surveillance — period {period}")

    def make_plan(feedback=None):
        raw = rule_plan(period) if plan_source == "rules" else model_plan(brain, period, feedback)
        plan, missing, rejected = check_plan(raw, period)
        log(f"Plan: {len(plan)} steps ({len(missing)} added from the checklist, {len(rejected)} rejected)")
        problems = [r["reason"] for r in rejected] + ([] if raw else ["the plan was empty or not a JSON list"])
        return plan, missing, rejected, problems

    plan, missing, rejected, problems = make_plan()
    replanned = False
    if problems and plan_source != "rules":             # the plan itself is unusable: replan before running
        log(f"Replanning once: {len(problems)} problem(s) in the plan")
        plan, missing, rejected, _ = make_plan(problems)
        replanned = True
    results = run_plan(plan, log)
    if errors(results) and plan_source != "rules" and not replanned:   # a step failed: replan once, rerun
        log(f"Replanning once: {len(errors(results))} step(s) failed")
        plan, missing, rejected, _ = make_plan(errors(results))
        results = run_plan(plan, log)
        replanned = True

    check = self_check(results, period)
    reason = check.get("error") or (None if check["agree"] else "the self-check disagrees")
    if reason is None and find(results, "draft_surveillance_note", period=period) is None:
        reason = "the note could not be drafted"
    if reason:
        log(f"Self-check: {reason}")
    else:
        log(f"Self-check: 90+ ratio {check['trigger_tool']:.6f} (trigger tool) vs {check['recomputed']:.6f} "
            f"(recomputed) — agree")

    changes = []
    if reason is None:                                   # memory records computed figures, not sent notes
        memory = load_memory(memory_dir)
        current = key_figures(results, period)
        prev_period, previous = latest_before(memory, period)
        changes = compare(previous, current, None if prev_period == period - 1 else prev_period)
        memory[str(period)] = current
        save_memory(memory_dir, memory)
        note = find(results, "draft_surveillance_note", period=period)["note_markdown"]
        note += "\n\n## Month on month\n" + "\n".join(f"- {c}" for c in changes)
        note += (f"\n\n## Self-check\n- 90+ day arrears ratio recomputed from two stratifications: "
                 f"{check['recomputed'] * 100:.4f}% — agrees with the trigger tool.")
        approved = ask_human(note) if approve is None else bool(approve)
        status = "sent" if approved else "held for approval"
    else:                                                # a failure holds the note, whatever the approval
        note = f"# Note held — period {period}\n\nReason: {reason}.\n\n" + \
               "\n".join(f"- {e}" for e in errors(results))
        approved, status = False, "held"
    folder = out_dir / ("outbox" if approved else "drafts")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"note_2026_{period:02d}.md"
    path.write_text(note, encoding="utf-8")
    log(f"Note {status}: {path.parent.name}/{path.name}")
    return {"period": period, "plan": plan, "missing_from_plan": missing, "rejected_from_plan": rejected,
            "replanned": replanned, "self_check": check, "changes": changes, "status": status,
            "reason": reason, "path": str(path), "note": note}


def main(argv=None):
    p = argparse.ArgumentParser(description="Run one month of agentic surveillance.")
    p.add_argument("--period", type=int, required=True)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--approve", dest="approve", action="store_true", default=None)
    g.add_argument("--no-approve", dest="approve", action="store_false")
    p.add_argument("--plan", default="rules", choices=["rules", "live", "record", "replay"])
    p.add_argument("--memory", default=None)
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)
    brain = None
    if a.plan != "rules":
        from agent_core.brains import make_brain
        rec = Path(__file__).resolve().parents[1] / "recordings" / f"agentic_plan_{a.period:02d}.jsonl"
        if a.plan == "replay" and not (rec.exists() and rec.stat().st_size):
            print("[Recording pending: run python record_all.py with Ollama installed, then rebuild]")
            return 0
        brain = make_brain(a.plan, rec)
    run_surveillance(a.period, a.plan, brain, a.memory, a.out, a.approve)
    return 0


if __name__ == "__main__":
    sys.exit(main())
