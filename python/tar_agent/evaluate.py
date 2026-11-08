"""The test set: 40 questions with expected answers, and a scorer.

The expected answers are COMPUTED here from the deal pack and the tools.
Nobody types them in, so they cannot contain a typing mistake.

    python -m tar_agent.evaluate build            writes data/eval/questions.jsonl
    python -m tar_agent.evaluate run --mode rules scores the agent on all 40 questions
"""

import argparse
import json
import re
import sys
from pathlib import Path

from .data import DATA_DIR, deal_terms, investor_report
from .tools.loan_tape import load_clean_tape, validate_loan_tape
from .tools.note import draft_surveillance_note
from .tools.prospectus import chunks
from .tools.stratify import stratify_pool
from .tools.triggers import first_breach_period, run_trigger_tests

QUESTIONS_FILE = DATA_DIR / "eval" / "questions.jsonl"
RECORDINGS = Path(__file__).resolve().parents[1] / "recordings" / "eval"


# --------------------------------------------------------------------------
# 1. Building the question set
# --------------------------------------------------------------------------

# Percentages are printed with two decimals, so 0.6550% may appear as 0.66%: allow 0.006 points.
PCT_TOL = 0.006


def number(value, tolerance):
    return {"kind": "number", "value": round(value, 6), "tolerance": tolerance}


def text(*words):
    return {"kind": "text", "contains": list(words)}


def page_of(fragment):
    """The first prospectus page whose text contains the fragment (found by reading, not by searching)."""
    for c in chunks():
        if fragment in c["text"]:
            return c["page"]
    raise ValueError(f"'{fragment}' is not in the prospectus")


def test_value(period, name):
    return next(t for t in run_trigger_tests(period)["tests"] if t["test"] == name)["value"]


def build_questions():
    terms = deal_terms()
    v = validate_loan_tape()
    qs = []

    def add(question, expected, tools, page=None):
        if page is not None:
            expected["page"] = page
        qs.append({"id": f"Q{len(qs) + 1:02d}", "question": question, "expected": expected, "tools": tools})

    # Loan tape (3)
    add("Validate the loan tape: how many issues did you find?", number(v["issues_found"], 0), ["validate_loan_tape"])
    add("Validate the loan tape: how many rows were received?", number(v["rows_received"], 0), ["validate_loan_tape"])
    add("Validate the loan tape: does the cleaned tape reconcile with the initial pool balance?",
        text("reconciles with" if v["reconciles"] else "does not reconcile"), ["validate_loan_tape"])

    # Trigger tests (17)
    for p in range(3, 13):
        add(f"What is the 90+ day arrears ratio in period {p}?",
            number(test_value(p, "arrears_90_ratio") * 100, PCT_TOL), ["run_trigger_tests"])
    for p in (6, 9, 11, 12):
        add(f"What is the cumulative default ratio in period {p}?",
            number(test_value(p, "cumulative_default_ratio") * 100, PCT_TOL), ["run_trigger_tests"])
    add("In which period was a trigger breached for the first time?", {**number(first_breach_period(), 0), "pattern": rf"first[^.]*\bperiod\s+{first_breach_period()}\b"},
        ["run_trigger_tests"])
    for p in (9, 11):
        mode = run_trigger_tests(p)["principal_payment_mode"]
        add(f"Is principal paid pro rata or sequentially in period {p}?",
            text("sequentially" if mode == "sequential" else "pro rata"), ["run_trigger_tests"])

    # Stratifications (7)
    for p in (10, 12):
        top = stratify_pool("region", p, "balance_90plus")["rows"][0]["group"]
        add(f"Which region holds most of the 90+ day arrears in period {p}?", text(top), ["stratify_pool"])
    nw = next(r for r in stratify_pool("region", 10, "balance_90plus")["rows"] if r["group"] == "North West")
    add("What share of the 90+ day arrears balance does the North West region hold in period 10?",
        number(nw["share_of_total"] * 100, PCT_TOL), ["stratify_pool"])
    london = next(r for r in stratify_pool("region", 0)["rows"] if r["group"] == "London")
    add("What is the balance of the London region at the cut-off date?", number(london["balance"], 0.01),
        ["stratify_pool"])
    pcp = next(r for r in stratify_pool("product", 0)["rows"] if r["group"] == "PCP")
    add("What share of the pool balance at the cut-off date is PCP?", number(pcp["share_of_total"] * 100, PCT_TOL),
        ["stratify_pool"])
    add("How many loans are outstanding in period 12?", number(stratify_pool("product", 12, "count")["total"], 0),
        ["stratify_pool"])
    add("Which fuel type has the largest balance at the cut-off date?",
        text(stratify_pool("fuel_type", 0)["rows"][0]["group"]), ["stratify_pool"])

    # Prospectus (9): the figure comes from the deal terms or the tape, the page from reading the PDF
    lim90 = f"{terms['triggers']['arrears_90_limit'] * 100:.2f}%"
    add("According to the prospectus, what is the limit for the 90+ day arrears ratio?",
        number(terms["triggers"]["arrears_90_limit"] * 100, 0), ["search_prospectus"],
        page_of(f"must not exceed {lim90}"))
    fee = terms["fees"]["servicer_fee_rate"] * 100
    add("According to the prospectus, what is the servicer fee?", number(fee, 0), ["search_prospectus"],
        page_of(f"servicer fee of {fee:.2f}%"))
    b = next(c for c in terms["classes"] if c["name"] == "B")
    add("According to the prospectus, what is the margin on the Class B notes?", number(b["margin"] * 100, 0),
        ["search_prospectus"], page_of(f"SONIA + {b['margin'] * 100:.2f}%"))
    rf = terms["reserve_fund_required_amount"]
    add("According to the prospectus, how much is the reserve fund on the closing date?", number(rf, 0.01),
        ["search_prospectus"], page_of(f"£{rf:,.2f}"))
    tf = terms["fees"]["trustee_fee_monthly"]
    add("According to the prospectus, what is the trustee fee?", number(tf, 0), ["search_prospectus"],
        page_of(f"trustee fee of £{tf:,.2f}"))
    last_lim = terms["triggers"]["cum_default_schedule"][-1]
    add("According to the prospectus, what is the cumulative default ratio limit for periods 7 to 12?",
        number(last_lim[2] * 100, 0), ["search_prospectus"], page_of(f"Periods 7 to 12 {last_lim[2] * 100:.2f}%"))
    tape = load_clean_tape()
    wa = (tape.interest_rate_pct * tape.current_balance).sum() / tape.current_balance.sum()
    add("According to the prospectus, what is the weighted average interest rate of the pool?",
        number(round(wa, 2), PCT_TOL), ["search_prospectus"], page_of(f"Weighted average interest rate {wa:.2f}%"))
    a = next(c for c in terms["classes"] if c["name"] == "A")
    add("According to the prospectus, what is the rating of the Class A notes at closing?", text(a["rating"]),
        ["search_prospectus"], page_of(f"{a['rating']}"))
    add("According to the prospectus, when is a loan defaulted?", text("4 instalments in arrears"),
        ["search_prospectus"], page_of("4 instalments in arrears"))

    # Monthly figures (4)
    add("What is the pool balance in period 12?", number(investor_report(12)["pool"]["closing_balance"], 1),
        ["draft_surveillance_note"])
    add("What were the defaults in period 10?", number(investor_report(10)["pool"]["defaults"], 1),
        ["draft_surveillance_note"])
    add("What were the prepayments in period 10?", number(investor_report(10)["pool"]["prepayments"], 1),
        ["draft_surveillance_note"])
    headline = draft_surveillance_note(10)["note_markdown"].split("**")[1]
    add("Draft the surveillance note for period 10.", text(headline), ["draft_surveillance_note"])
    return qs


def write_questions(path=QUESTIONS_FILE):
    path.parent.mkdir(parents=True, exist_ok=True)
    qs = build_questions()
    path.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in qs), encoding="utf-8")
    return qs


def load_questions(path=QUESTIONS_FILE):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


# --------------------------------------------------------------------------
# 2. Scoring one answer
# --------------------------------------------------------------------------

def numbers_in(answer):
    """Every number written in the answer: '£1,111,137.93' -> 1111137.93, '1.32%' -> 1.32."""
    return [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", answer or "")]


def score_answer(answer, expected):
    """Return (correct, reason)."""
    answer = answer or ""
    if expected["kind"] == "number":
        found = numbers_in(answer)
        ok = any(abs(x - expected["value"]) <= expected["tolerance"] for x in found)
        reason = "figure found" if ok else f"expected {expected['value']} (± {expected['tolerance']})"
    else:
        missing = [w for w in expected["contains"] if w.lower() not in answer.lower()]
        ok = not missing
        reason = "text found" if ok else f"missing: {missing}"
    if ok and "pattern" in expected and not re.search(expected["pattern"], answer, re.I):
        ok, reason = False, f"figure not in the expected phrase ({expected['pattern']})"
    if ok and "page" in expected and not re.search(rf"\bpage {expected['page']}\b", answer, re.I):
        ok, reason = False, f"page {expected['page']} not cited"
    return ok, reason


# --------------------------------------------------------------------------
# 3. Running the whole test set
# --------------------------------------------------------------------------

def run_evaluation(mode="rules", questions=None):
    from .agent import ask
    questions = questions or load_questions()
    results = []
    for q in questions:
        recording = RECORDINGS / f"{q['id']}.jsonl"
        if mode == "replay" and not (recording.exists() and recording.stat().st_size):
            results.append({"id": q["id"], "correct": False, "reason": "recording pending", "tools_used": []})
            continue
        run = ask(q["question"], mode, recording, log=lambda m: None)
        ok, reason = score_answer(run["answer"], q["expected"])
        used = [s["name"] for s in run["steps"] if s["type"] == "tool"]
        results.append({"id": q["id"], "correct": ok, "reason": reason, "tools_used": used,
                        "right_tools": set(q["tools"]) <= set(used), "steps": len(run["steps"])})
    score = sum(r["correct"] for r in results)
    return {"mode": mode, "score": score, "out_of": len(results), "results": results}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["build", "run"])
    p.add_argument("--mode", default="rules", choices=["rules", "live", "record", "replay"])
    a = p.parse_args(argv)
    if a.command == "build":
        qs = write_questions()
        print(f"Wrote {len(qs)} questions to data/eval/questions.jsonl")
        return 0
    if a.mode == "replay" and not RECORDINGS.exists():
        print("[Recording pending: run python record_all.py with Ollama installed, then rebuild]")
        return 0
    out = run_evaluation(a.mode)
    for r in out["results"]:
        if not r["correct"]:
            print(f"{r['id']}  WRONG  {r['reason']}")
    print(f"Score ({out['mode']} mode): {out['score']} / {out['out_of']}")
    print(f"Questions answered with the expected tools: {sum(r.get('right_tools', False) for r in out['results'])}"
          f" / {out['out_of']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
