"""Chapter 9: the two trigger tests for all twelve periods."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.tools.triggers import run_trigger_tests

print(f"{'Period':>6} {'90+ ratio':>10} {'limit':>7} {'Cum. default ratio':>18} {'limit':>7}  mode")
for period in range(1, 13):
    r = run_trigger_tests(period)
    t = {x["test"]: x for x in r["tests"]}
    a, c = t["arrears_90_ratio"], t["cumulative_default_ratio"]
    flag = " <- breach" if a["breached"] or c["breached"] else ""
    print(f"{period:>6} {a['value']:>10.2%} {a['limit']:>7.2%} {c['value']:>18.2%} {c['limit']:>7.2%}  "
          f"{r['principal_payment_mode']}{flag}")
