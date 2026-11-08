"""Chapter 2: the behaviour assumptions behind the simulation, and the path of the two trigger ratios.

Run from the repository root:
    python python/vol2/ch02/calibration.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "generator"))
from deal_terms import BEHAVIOUR, SEED  # noqa: E402

print(f"Seed: {SEED}")
for key, value in BEHAVIOUR.items():
    print(f"  {key:<24}{value}")
print()
terms = json.loads((ROOT / "data" / "deal_terms.json").read_text())
limit = terms["triggers"]["arrears_90_limit"]
print(f"{'Period':>6}{'90+ ratio':>11}{'Limit':>8}{'Cumulative defaults':>21}{'Payment':>12}")
for period in range(1, 13):
    r = json.loads((ROOT / "data" / "investor_reports" / f"investor_report_2026_{period:02d}.json").read_text())
    t = r["triggers"]
    print(f"{period:>6}{t['arrears_90_ratio']['value']:>11.2%}{limit:>8.2%}"
          f"{t['cumulative_default_ratio']['value']:>21.2%}{'sequential' if t['sequential_payment'] else 'pro rata':>12}")
