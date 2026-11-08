"""Chapter 8: three stratifications of the pool."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.tools.stratify import stratify_pool


def show(title, s):
    measure = s["measure"]
    print(title)
    for r in s["rows"]:
        extra = f"  within region {r['ratio_within_group']:6.2%}" if "ratio_within_group" in r else ""
        print(f"  {r['group']:<26} {r[measure]:>16,.2f}  {r['share_of_total']:7.2%}{extra}")
    print(f"  {'Total':<26} {s['total']:>16,.2f}")
    print()


show("1. Balance by product at the cut-off date", stratify_pool("product", 0))
show("2. Balance by credit score band at the cut-off date", stratify_pool("credit_score_band", 0))
show("3. 90+ day arrears by region, end of period 10", stratify_pool("region", 10, "balance_90plus"))
