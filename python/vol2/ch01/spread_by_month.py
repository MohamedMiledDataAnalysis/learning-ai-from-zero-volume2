"""Chapter 1, exercise 1.7: excess spread and deferred consideration for every month.

Run from the repository root:
    python python/vol2/ch01/spread_by_month.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from solution_ch01 import excess_spread  # noqa: E402
from tar_agent.data import investor_report  # noqa: E402

print(f"{'Period':>6}{'Excess spread':>15}{'Defaults':>13}{'Recoveries':>12}{'To originator':>15}")
for period in range(1, 13):
    rep = investor_report(period)
    p = rep["pool"]
    print(f"{period:>6}{excess_spread(period):>15,.2f}{p['defaults']:>13,.2f}{p['recoveries']:>12,.2f}"
          f"{rep['residual_to_originator']:>15,.2f}")
