"""Final exam, section C1: a trigger script written by a junior colleague. It contains three bugs.

Run from the repository root:  python python/vol2/final_exam/buggy_triggers.py
"""

import json
from pathlib import Path

import pandas as pd

perf = pd.read_csv("data/loan_performance.csv")
terms = json.loads(Path("data/deal_terms.json").read_text(encoding="utf-8"))

for period in range(9, 13):
    p = perf[perf.period == period]
    live = p[p.status.isin(["Current", "Arrears"])]
    pool = live.closing_balance.sum()
    arrears_90 = live[live.instalments_in_arrears > 3].closing_balance.sum()
    cum_defaults = perf[perf.period <= period].defaulted_balance.sum()
    cum_ratio = cum_defaults / pool
    ratio = arrears_90 / pool
    breached = ratio > 1.25
    print(f"period {period}: 90+ ratio {ratio:.2%}  cumulative default ratio {cum_ratio:.2%}  breached={breached}")
