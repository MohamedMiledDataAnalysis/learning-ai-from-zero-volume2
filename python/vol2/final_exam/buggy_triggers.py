"""Final exam, section C1: a trigger script written by a junior colleague. It contains three bugs.

Run from the repository root:  python python/vol2/final_exam/buggy_triggers.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, "python")
from tar_agent.data import loan_performance  # noqa: E402

perf = loan_performance()
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
