"""Chapter 2: the North West story, told by the servicer reports.

For each period: the 90+ day arrears ratio inside the North West and in the rest of the pool,
and the North West's share of all 90+ arrears.

Run from the repository root:
    python python/vol2/ch02/north_west.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.data import servicer_report  # noqa: E402   the Regional sheet of Kestrel's servicer report

print(f"{'Period':>6}{'NW 90+ ratio':>14}{'Rest 90+ ratio':>16}{'NW share of 90+':>17}{'NW share of pool':>18}")
for period in range(1, 13):
    s = servicer_report(period)
    nw = s[s.region == "North West"].iloc[0]
    rest = s[s.region != "North West"]
    total_90 = s.balance_3_in_arrears.sum()
    nw_share = nw.balance_3_in_arrears / total_90 if total_90 else 0.0
    print(f"{period:>6}{nw.balance_3_in_arrears / nw.balance:>14.2%}"
          f"{rest.balance_3_in_arrears.sum() / rest.balance.sum():>16.2%}"
          f"{nw_share:>17.1%}{nw.balance / s.balance.sum():>18.1%}")
