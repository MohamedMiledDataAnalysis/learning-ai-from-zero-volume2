"""The structured finance agent: the five tools, the shared loop, and a brain.

Run from the python/ folder:

    python -m tar_agent.agent "Run the trigger tests for period 10." --mode rules
    python -m tar_agent.agent "Run the trigger tests for period 10." --mode live      (needs Ollama)

Modes:
    rules   FinanceRules below decides every step: no model, same result on every computer
    live    a local model in Ollama decides
    record  like live, and every model reply is saved to a recording
    replay  plays back a recording: the same replies as the recorded run
"""

import argparse
import json
import re
import sys
from pathlib import Path

from agent_core.brains import make_brain
from agent_core.loop import run_agent

from .registry import call_tool, tool_schemas

SYSTEM_PROMPT = """You are a surveillance analyst's assistant for the securitisation Thames Auto Receivables 2026-1 plc.
You answer questions about the deal using ONLY the tools provided. Rules:
1. Every figure in your answer must come from a tool result. Never estimate or invent a figure.
2. For questions about the deal's rules (limits, fees, definitions), call search_prospectus and cite the page as "page N".
3. Periods are numbered 1 (January 2026) to 12 (December 2026). Period 0 means the cut-off date, 31 December 2025.
4. Give percentages with two decimals (1.32%) and amounts in pounds with commas (£49,151,532.52).
5. If a tool returns an error, read it, correct your call, and try again.
6. Keep the final answer short: two to five sentences."""

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], start=1)}

RECORDINGS = Path(__file__).resolve().parents[1] / "recordings"


# --------------------------------------------------------------------------
# Reading a question: which period does it mean?
# --------------------------------------------------------------------------

def find_period(text):
    """Return the period a question refers to: 0 for the cut-off date, 1-12, or None."""
    t = text.lower()
    if "cut-off" in t or "cut off" in t:
        return 0
    m = re.search(r"period (\d{1,2})", t)
    if m:
        return int(m.group(1))
    for name, number in MONTHS.items():
        if re.search(rf"\b{name}\b", t) and (name != "may" or re.search(r"\bMay\b", text)):  # "may" counts only as "May"
            return number
    return None


# --------------------------------------------------------------------------
# Formatting tool results as sentences
# --------------------------------------------------------------------------

def pct(x):
    return f"{x * 100:.2f}%"


def money(x):
    return f"£{x:,.2f}"


def answer_from_result(question, name, result):
    """Turn one tool result into the final answer sentence(s)."""
    if "error" in result:
        return f"The tool {name} returned an error: {result['error']}"
    if name == "validate_loan_tape":
        rules = ", ".join(f"{k} ({v})" for k, v in result["issues_by_rule"].items())
        verdict = "reconciles" if result["reconciles"] else "does NOT reconcile"
        return (f"The tape received has {result['rows_received']:,} rows. Validation found "
                f"{result['issues_found']} issues: {rules}. After cleaning, {result['loans_after_cleaning']:,} loans "
                f"remain with a balance of {money(result['balance_after_cleaning'])}, which {verdict} with the "
                f"initial pool balance of {money(result['initial_pool_balance_in_deal_terms'])}.")
    if name == "run_trigger_tests":
        tests = {t["test"]: t for t in result["tests"]}
        a, c = tests["arrears_90_ratio"], tests["cumulative_default_ratio"]
        first = (f"The first trigger breach was in period {result['first_breach_period']}."
                 if result["first_breach_period"] else "No trigger has been breached so far.")
        return (f"In period {result['period']}, the 90+ day arrears ratio is {pct(a['value'])} against a limit of "
                f"{pct(a['limit'])} ({'breached' if a['breached'] else 'pass'}), and the cumulative default ratio is "
                f"{pct(c['value'])} against a limit of {pct(c['limit'])} "
                f"({'breached' if c['breached'] else 'pass'}). Principal is paid "
                f"{'sequentially' if result['principal_payment_mode'] == 'sequential' else 'pro rata'}. "
                f"{first}")
    if name == "stratify_pool":
        rows = result["rows"]
        top = rows[0]
        when = "at the cut-off date" if result["period"] == 0 else f"at the end of period {result['period']}"
        measure = result["measure"]
        if measure == "count":
            return f"There are {result['total']:,.0f} loans in the pool {when}. The largest group is {top['group']} ({top['count']:,.0f} loans)."
        wanted = next((r for r in rows if r["group"].lower() in question.lower()), top)
        label = "90+ day arrears balance" if measure == "balance_90plus" else "balance"
        text = (f"{when.capitalize()}, {wanted['group']} holds {money(wanted[measure])} of the {label}, which is "
                f"{pct(wanted['share_of_total'])} of the total of {money(result['total'])}.")
        if wanted is top:
            return text + " It is the largest group."
        return text + f" The largest group is {top['group']} with {pct(top['share_of_total'])}."
    if name == "search_prospectus":
        best = result["results"][0]
        return f"According to the prospectus (page {best['page']}, {best['section']}): \"{best['text']}\""
    if name == "draft_surveillance_note":
        return result["note_markdown"]
    return json.dumps(result)


# --------------------------------------------------------------------------
# The rule brain for the finance agent
# --------------------------------------------------------------------------

def choose_tool(question):
    """Decide which tool answers a question, and with which arguments. Plain keyword rules."""
    q = question.lower()
    period = find_period(question)
    if "prospectus" in q:
        # Search for the subject of the question, not for the word "prospectus": in a 136-page prospectus that
        # word is on many pages and would pull them up.
        query = re.sub(r"(?i)^according to the prospectus,?\s*", "", question)
        return "search_prospectus", {"query": query}
    if "loan tape" in q:
        return "validate_loan_tape", {}
    # Order matters: the stratification words are checked before "pool balance",
    # otherwise "What share of the pool balance is PCP?" would go to the note tool.
    if any(w in q for w in ["region", "fuel", "pcp", "product", "how many loans"]):
        by = "region" if "region" in q else "fuel_type" if "fuel" in q else "product"
        measure = "count" if "how many loans" in q else "balance_90plus" if "90+" in q else "balance"
        return "stratify_pool", {"by": by, "period": period or 0, "measure": measure}
    if "note" in q or "pool balance" in q or "defaults" in q or "prepayments" in q:
        return "draft_surveillance_note", {"period": period}
    if any(w in q for w in ["trigger", "arrears ratio", "default ratio", "breach", "pro rata", "sequential"]):
        return "run_trigger_tests", {"period": period or 12}
    return None, None


def finance_rules(memory):
    """RuleBrain for the finance agent: one tool call, then an answer built from its result."""
    question = next(m["content"] for m in memory if m["role"] == "user")
    last = memory[-1]
    if last["role"] == "user":
        name, args = choose_tool(question)
        if name is None:
            return {"content": "I can only answer questions about the loan tape, the pool, the trigger tests, "
                               "the prospectus and the monthly note.", "tool_calls": []}
        return {"content": "", "tool_calls": [{"name": name, "arguments": args}]}
    result = json.loads(last["content"])
    return {"content": answer_from_result(question, last["tool_name"], result), "tool_calls": []}


# --------------------------------------------------------------------------
# Running the agent
# --------------------------------------------------------------------------

def ask(question, mode="rules", recording=None, log=print, max_steps=6):
    """Ask the agent one question. Returns the run (answer, steps, memory)."""
    brain = make_brain(mode, recording, rules=finance_rules)
    return run_agent(question, brain, tool_schemas(), call_tool, SYSTEM_PROMPT, max_steps=max_steps, log=log)


def main(argv=None):
    p = argparse.ArgumentParser(description="Ask the structured finance agent a question.")
    p.add_argument("question")
    p.add_argument("--mode", default="rules", choices=["rules", "live", "record", "replay"])
    p.add_argument("--recording", default=str(RECORDINGS / "agent_question.jsonl"))
    p.add_argument("--quiet", action="store_true", help="print the answer only, not the steps")
    a = p.parse_args(argv)
    if a.mode == "replay" and not (Path(a.recording).exists() and Path(a.recording).stat().st_size):
        print("[Recording pending: run python record_all.py with Ollama installed, then rebuild]")
        return 0
    out = ask(a.question, a.mode, a.recording, log=(lambda m: None) if a.quiet else print)
    print()
    print("Answer:", out["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
