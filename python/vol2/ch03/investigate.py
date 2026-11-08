"""Chapter 3, applied example: a plan written by hand for the goal "Explain the October breach", then run.

Run from the repository root:
    python python/vol2/ch03/investigate.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.registry import call_tool  # noqa: E402

PLAN = [
    ("run_trigger_tests", {"period": 9}, "the month before: how close to the limit?"),
    ("run_trigger_tests", {"period": 10}, "the month of the breach"),
    ("stratify_pool", {"by": "region", "period": 10, "measure": "balance_90plus"}, "where are the 90+ arrears?"),
    ("stratify_pool", {"by": "credit_score_band", "period": 10, "measure": "balance_90plus"},
     "is it a credit-quality problem?"),
    ("search_prospectus", {"query": "consequence trigger event principal sequentially", "top_k": 1},
     "what does the contract say happens now?"),
]

for i, (tool, args, why) in enumerate(PLAN, start=1):
    r = json.loads(call_tool(tool, args))
    print(f"{i}. {tool}({json.dumps(args)}) — {why}")
    if tool == "run_trigger_tests":
        t = next(x for x in r["tests"] if x["test"] == "arrears_90_ratio")
        print(f"   90+ ratio {t['value']:.2%}, headroom {t['headroom'] * 100:+.2f} points, mode {r['principal_payment_mode']}")
    elif tool == "stratify_pool":
        for row in r["rows"][:2]:
            print(f"   {row['group']}: {row['share_of_total']:.1%} of the 90+ balance; "
                  f"{row['ratio_within_group']:.2%} of its own balance is 90+")
    else:
        top = r["results"][0]
        print(f"   page {top['page']}: {top['text'][:96]}...")
