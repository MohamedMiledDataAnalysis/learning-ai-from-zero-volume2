"""Chapter 9: how principal was shared between the classes before and after the breach."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.data import investor_report

for period in (9, 10):
    rep = investor_report(period)
    mode = "sequential" if rep["triggers"]["sequential_payment"] else "pro rata"
    print(f"Period {period} ({mode}): payment date {rep['payment_date']}")
    total = sum(n["principal_paid"] for n in rep["notes"])
    for n in rep["notes"]:
        share = n["principal_paid"] / total
        print(f"  Class {n['class']}: opening £{n['opening_balance']:>14,.2f}  principal £{n['principal_paid']:>12,.2f}"
              f"  ({share:6.2%})")
    print()
