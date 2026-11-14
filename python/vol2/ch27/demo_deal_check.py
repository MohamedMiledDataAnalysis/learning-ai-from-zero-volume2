"""Chapter 27: the deal check in Dash's logic. The Thames prospectus, its pool-cut tape and the investor report
for period 10, as an Excel copy this time, checked against each other.

Run from the repository root:  python python/vol2/ch27/demo_deal_check.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402

terms = logic.run_extraction(logic.sample_document("thames")["path"], "rules", "simulated")["terms"]
template, supplementary = logic.tape_files([str(logic.SUPPLEMENTARY), str(logic.POOL_CUT)])
report = logic.investor_report_path(10).with_suffix(".xlsx")        # the Excel copy of Larkmead's report
rows = logic.deal_check(terms, template, str(report), supplementary)
counts = {r: sum(row["result"] == r for row in rows) for r in ("pass", "FAIL", "BREACHED")}
print(f"{len(rows)} checks: " + ", ".join(f"{n} {r}" for r, n in counts.items()))
for row in rows:
    if row["result"] != "pass":
        print(f"  {row['result']}: {row['check']} (page {row['prospectus page']}): {row['found']}")
