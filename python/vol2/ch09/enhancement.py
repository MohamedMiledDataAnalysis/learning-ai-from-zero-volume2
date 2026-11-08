"""Chapter 9: Class A's protection (subordination) before and after the switch to sequential payment."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.data import investor_report  # noqa: E402

print(f"{'Period':>6} {'Notes total':>15} {'Pool balance':>15} {'Class A':>15} {'Subordination':>14} {'Shortfall':>10}")
for period in (8, 9, 10, 11, 12):
    rep = investor_report(period)
    notes = {n["class"]: n["closing_balance"] for n in rep["notes"]}
    total = sum(notes.values())
    pool = rep["pool"]["closing_balance"]
    below_a = total - notes["A"]                 # Classes B, C and D absorb losses before Class A
    print(f"{period:>6} {total:>15,.2f} {pool:>15,.2f} {notes['A']:>15,.2f} {below_a / total:>14.2%} "
          f"{max(total - pool, 0):>10,.2f}")
