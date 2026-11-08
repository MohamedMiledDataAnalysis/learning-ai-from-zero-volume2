"""Tool 2 — pool stratifications.

A stratification splits the pool into groups (by region, by product, by credit
score band...) and shows how much balance sits in each group. Analysts use it
to see what the pool is made of and where problems are concentrated.

The tool works on the cut-off pool or on the pool at the end of any period, and
can measure the total balance, the number of loans, or the 90+ day arrears
balance.
"""

import pandas as pd

from ..data import check_period, loan_performance
from .loan_tape import load_clean_tape

# Bands match the tables in section 3 of the prospectus.
BANDS = {
    "credit_score_band": ("credit_score", [-1, 649, 699, 749, 799, 849, 999],   # -1: a score of 0 is valid
                          ["Below 650", "650-699", "700-749", "750-799", "800-849", "850 and above"]),
    "interest_rate_band": ("interest_rate_pct", [0, 7.99, 8.99, 9.99, 10.99, 99],
                           ["Below 8.00%", "8.00-8.99%", "9.00-9.99%", "10.00-10.99%", "11.00% and above"]),
    "ltv_band": ("ltv_original_pct", [0, 79.99, 84.99, 89.99, 94.99, 100],
                 ["Below 80%", "80-84.99%", "85-89.99%", "90-94.99%", "95-100%"]),
}
FIELDS = ["region", "product", "vehicle_type", "fuel_type", "employment_status", *BANDS]
MEASURES = ["balance", "count", "balance_90plus"]


def pool_at(period):
    """The live loans with their balances: at the cut-off date (period 0) or at the end of a period."""
    tape = load_clean_tape()
    if period == 0:
        pool = tape.assign(balance=tape.current_balance, instalments_in_arrears=0)
    else:
        check_period(period)
        perf = loan_performance()
        p = perf[(perf.period == period) & perf.status.isin(["Current", "Arrears"])]
        pool = tape.merge(p[["loan_id", "closing_balance", "instalments_in_arrears"]], on="loan_id")
        pool = pool.rename(columns={"closing_balance": "balance"})
    for name, (col, edges, labels) in BANDS.items():
        # A loan whose value is missing goes in a "Missing" group, so no balance is lost from the total.
        pool[name] = pd.cut(pool[col].astype("Float64"), edges, labels=labels).cat.add_categories("Missing")
        pool[name] = pool[name].fillna("Missing")
    return pool


def stratify_pool(by, period=0, measure="balance"):
    """Tool entry point.

    by      one of FIELDS
    period  0 for the cut-off date, 1 to 12 for the end of a collection period
    measure 'balance', 'count' or 'balance_90plus'
    """
    if by not in FIELDS:
        raise ValueError(f"'by' must be one of {FIELDS}")
    if measure not in MEASURES:
        raise ValueError(f"'measure' must be one of {MEASURES}")
    pool = pool_at(period)
    pool["value"] = {
        "balance": pool.balance,
        "count": 1,
        "balance_90plus": pool.balance.where(pool.instalments_in_arrears >= 3, 0.0),
    }[measure]
    g = pool.groupby(by, observed=True).agg(value=("value", "sum"), pool_balance=("balance", "sum"))
    total = float(g.value.sum())
    rows = []
    for key, r in g.sort_values("value", ascending=False, kind="stable").iterrows():
        row = {"group": str(key), measure: round(float(r.value), 2),
               "share_of_total": round(float(r.value) / total, 6) if total else 0.0}
        if measure == "balance_90plus":
            # How much of the group's own balance is 90+ in arrears: shows concentration.
            row["ratio_within_group"] = round(float(r.value) / float(r.pool_balance), 6) if r.pool_balance else 0.0
        rows.append(row)
    return {"period": period, "by": by, "measure": measure,
            "total": round(total, 2), "loans_in_pool": int(len(pool)), "rows": rows}
