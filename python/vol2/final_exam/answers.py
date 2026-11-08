"""Final exam, section B: every expected figure, computed from the deal pack.

Run from the repository root:  python python/vol2/final_exam/answers.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent
from tar_agent.data import deal_terms, investor_report  # noqa: E402
from tar_agent.tools.stratify import stratify_pool  # noqa: E402


def pool_factor(period):
    """Pool balance at the end of the period divided by the pool balance at the cut-off date."""
    return investor_report(period)["pool"]["closing_balance"] / deal_terms()["initial_pool_balance"]


def subordination(period, cls="A"):
    """Share of the notes ranked below a class, after the payment date."""
    notes = investor_report(period)["notes"]
    order = [n["class"] for n in notes]
    below = sum(n["closing_balance"] for n in notes if order.index(n["class"]) > order.index(cls))
    return below / sum(n["closing_balance"] for n in notes)


def smm_and_cpr(period):
    """Single monthly mortality (SMM) and its annual equivalent, the constant prepayment rate (CPR).
    SMM = prepayments / (opening balance - principal received from instalments)."""
    p = investor_report(period)["pool"]
    smm = p["prepayments"] / (p["opening_balance"] - p["principal_received"])
    return smm, 1 - (1 - smm) ** 12


def excess_spread(period):
    """Interest collections minus senior fees and note interest, in pounds and as an annual % of the opening pool."""
    rep = investor_report(period)
    paid = {w["item"]: w["paid"] for w in rep["waterfall"]}
    costs = sum(v for k, v in paid.items() if "fee" in k or "interest" in k)
    amount = rep["pool"]["interest_collections"] - costs
    return amount, 12 * amount / rep["pool"]["opening_balance"]


def north_west_arrears(period):
    rows = stratify_pool("region", period, "balance_90plus")["rows"]
    nw = next(r for r in rows if r["group"] == "North West")
    return nw["share_of_total"], nw["ratio_within_group"]


def all_answers():
    smm, cpr = smm_and_cpr(10)
    es_amount, es_pct = excess_spread(10)
    share, own = north_west_arrears(12)
    return {
        "B1 pool factor, period 12": f"{pool_factor(12):.4f}",
        "B2 Class A subordination, period 9": f"{subordination(9):.2%}",
        "B2 Class A subordination, period 12": f"{subordination(12):.2%}",
        "B3 SMM, period 10": f"{smm:.4%}",
        "B3 CPR, period 10": f"{cpr:.2%}",
        "B4 North West share of 90+ balance, period 12": f"{share:.2%}",
        "B4 North West own 90+ ratio, period 12": f"{own:.2%}",
        "B5 excess spread, period 10 (GBP)": f"£{es_amount:,.2f}",
        "B5 excess spread, period 10 (annual % of pool)": f"{es_pct:.2%}",
    }


if __name__ == "__main__":
    for key, value in all_answers().items():
        print(f"{key:<48} {value}")
