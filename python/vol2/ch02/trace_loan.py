"""Chapter 2: follow one loan through the deal pack — the first North West loan to default in October 2026.

Run from the repository root:
    python python/vol2/ch02/trace_loan.py [loan_id]
"""
import sys
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[3] / "data"
perf = pd.read_csv(DATA / "loan_performance.csv")
tape = pd.read_csv(DATA / "loan_tape_2026_12.csv")

if len(sys.argv) > 1:
    loan_id = sys.argv[1]
else:
    nw = set(tape.loc[tape.region == "North West", "loan_id"])
    defaulted = perf[(perf.period == 10) & (perf.status == "Defaulted") & perf.loan_id.isin(nw)]
    loan_id = sorted(defaulted.loan_id)[0]

info = tape[tape.loan_id == loan_id].iloc[0]
print(f"Loan {loan_id}: {info['product']}, {info['region']}, credit score {info['credit_score']}, "
      f"rate {info['interest_rate_pct']}%")
rows = perf[perf.loan_id == loan_id]
print(f"{'Period':>6}{'Opening':>11}{'Paid':>6}{'Principal':>11}{'Default':>11}{'Closing':>11}{'Behind':>8}  Status")
for r in rows.itertuples():
    print(f"{r.period:>6}{r.opening_balance:>11,.2f}{r.instalments_paid:>6}{r.principal_paid:>11,.2f}"
          f"{r.defaulted_balance:>11,.2f}{r.closing_balance:>11,.2f}{r.instalments_in_arrears:>8}  {r.status}")
