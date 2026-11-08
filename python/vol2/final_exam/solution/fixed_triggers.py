"""Final exam, section C1 solution: the trigger script with its three bugs fixed.

Run from the repository root:  python python/vol2/final_exam/solution/fixed_triggers.py
"""

import json
from pathlib import Path

import pandas as pd

perf = pd.read_csv("data/loan_performance.csv")
terms = json.loads(Path("data/deal_terms.json").read_text(encoding="utf-8"))
limit_90 = terms["triggers"]["arrears_90_limit"]                     # fix 3: the limit comes from the deal terms

for period in range(9, 13):
    p = perf[perf.period == period]
    live = p[p.status.isin(["Current", "Arrears"])]
    pool = live.closing_balance.sum()
    arrears_90 = live[live.instalments_in_arrears >= 3].closing_balance.sum()   # fix 1: 3 or more instalments
    cum_defaults = perf[perf.period <= period].defaulted_balance.sum()
    cum_ratio = cum_defaults / terms["initial_pool_balance"]                # fix 2: divide by the INITIAL pool balance
    ratio = arrears_90 / pool
    breached = ratio > limit_90
    print(f"period {period}: 90+ ratio {ratio:.2%}  cumulative default ratio {cum_ratio:.2%}  breached={breached}")
