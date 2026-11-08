"""Tool 5 — draft the monthly surveillance note.

A surveillance analyst writes a short note each month: how the pool performed,
whether any trigger failed, what is driving the change, and what to watch.

This tool builds the factual draft from the other tools, with every figure
computed and none invented. The model may later improve the wording, but the
numbers come from here.
"""

from ..data import check_period, investor_report
from .stratify import stratify_pool
from .triggers import run_trigger_tests


def pct(x, dp=2):
    return f"{x * 100:.{dp}f}%"


def money(x):
    return f"£{x:,.0f}"


def draft_surveillance_note(period):
    """Tool entry point: the note as Markdown, plus the key figures it uses."""
    check_period(period)
    rep = investor_report(period)
    trig = run_trigger_tests(period)
    pool = rep["pool"]
    a90 = next(t for t in trig["tests"] if t["test"] == "arrears_90_ratio")
    cdr = next(t for t in trig["tests"] if t["test"] == "cumulative_default_ratio")
    prev_a90 = (next(t for t in run_trigger_tests(period - 1)["tests"] if t["test"] == "arrears_90_ratio")["value"]
                if period > 1 else 0.0)

    regions = stratify_pool("region", period, "balance_90plus")["rows"]
    top = regions[0] if regions and regions[0]["balance_90plus"] > 0 else None
    pool_share = None
    if top:
        by_balance = {r["group"]: r["share_of_total"] for r in stratify_pool("region", period, "balance")["rows"]}
        pool_share = by_balance[top["group"]]

    if trig["trigger_event_this_period"] and trig["first_breach_period"] == period:
        headline = "A trigger event occurred this period. Principal is now paid sequentially."
    elif trig["principal_payment_mode"] == "sequential":
        headline = (f"Principal remains sequential since the trigger event in period {trig['first_breach_period']}.")
    else:
        headline = "All trigger tests passed. Principal continues to be paid pro rata."

    lines = [
        f"# Surveillance note — {rep['deal']}",
        f"Collection period {period} (ending {rep['collection_period_end']}), payment date {rep['payment_date']}",
        "",
        f"**{headline}**",
        "",
        "## Pool",
        f"- Pool balance fell from {money(pool['opening_balance'])} to {money(pool['closing_balance'])} "
        f"({pool['loans_outstanding']:,} loans).",
        f"- Prepayments: {money(pool['prepayments'])}. Defaults: {money(pool['defaults'])}. "
        f"Recoveries: {money(pool['recoveries'])}.",
        "",
        "## Trigger tests",
        f"- 90+ day arrears ratio: {pct(a90['value'])} against a limit of {pct(a90['limit'])} — "
        f"{'BREACHED' if a90['breached'] else 'pass'} (previous period {pct(prev_a90)}).",
        f"- Cumulative default ratio: {pct(cdr['value'])} against a limit of {pct(cdr['limit'])} — "
        f"{'BREACHED' if cdr['breached'] else 'pass'}.",
        f"- Reserve fund: {money(rep['reserve_fund']['balance'])} "
        f"(required {money(rep['reserve_fund']['required'])}).",
        f"- Figures recomputed from the loan-level data "
        f"{'agree' if all(t['agrees_with_report'] for t in trig['tests']) else 'DO NOT agree'} with the investor report.",
    ]
    if top:
        lines += [
            "",
            "## Driver",
            f"- {top['group']} holds {pct(top['share_of_total'], 1)} of the 90+ day arrears balance "
            f"but {pct(pool_share, 1)} of the pool balance. "
            f"{pct(top['ratio_within_group'], 1)} of its balance is 90+ days in arrears.",
        ]
    lines += ["", "## Notes",
              *[f"- Class {n['class']}: {money(n['closing_balance'])} after {money(n['principal_paid'])} of principal."
                for n in rep["notes"]]]
    if rep["principal_deficiency"] > 0:      # the notes exceed the pool: investors must be told
        lines.append(f"- Principal deficiency after the payment date: {money(rep['principal_deficiency'])}.")
    return {
        "period": period,
        "note_markdown": "\n".join(lines),
        "key_figures": {
            "arrears_90_ratio": a90["value"], "cumulative_default_ratio": cdr["value"],
            "principal_payment_mode": trig["principal_payment_mode"],
            "main_arrears_region": top["group"] if top else None,
        },
    }
