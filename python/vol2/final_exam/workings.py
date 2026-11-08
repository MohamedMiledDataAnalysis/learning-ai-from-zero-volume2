"""Final exam, section B: the worked calculations, step by step, from the investor reports.

Run from the repository root:  python python/vol2/final_exam/workings.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent
from tar_agent.data import deal_terms, investor_report  # noqa: E402
from tar_agent.tools.stratify import stratify_pool  # noqa: E402

initial = deal_terms()["initial_pool_balance"]
r12, r9, r10 = investor_report(12), investor_report(9), investor_report(10)

print("B1  pool factor = closing pool balance, period 12 / initial pool balance")
print(f"    = {r12['pool']['closing_balance']:,.2f} / {initial:,.2f} = {r12['pool']['closing_balance'] / initial:.4f}")

for rep in (r9, r12):
    n = {x["class"]: x["closing_balance"] for x in rep["notes"]}
    below, total = n["B"] + n["C"] + n["D"], sum(n.values())
    print(f"B2  period {rep['period']}: B + C + D = {n['B']:,.2f} + {n['C']:,.2f} + {n['D']:,.2f} = {below:,.2f}")
    print(f"    all notes = {total:,.2f};  subordination of A = {below:,.2f} / {total:,.2f} = {below / total:.2%}")

gap = sum(x["closing_balance"] for x in r12["notes"]) - r12["pool"]["closing_balance"]
print(f"    period 12: notes {sum(x['closing_balance'] for x in r12['notes']):,.2f} - pool "
      f"{r12['pool']['closing_balance']:,.2f} = principal deficiency {gap:,.2f}")

p = r10["pool"]
base = p["opening_balance"] - p["principal_received"]
smm = p["prepayments"] / base
print("B3  SMM = prepayments / (opening balance - principal received), period 10")
print(f"    = {p['prepayments']:,.2f} / ({p['opening_balance']:,.2f} - {p['principal_received']:,.2f})"
      f" = {p['prepayments']:,.2f} / {base:,.2f} = {smm:.4%}")
print(f"    CPR = 1 - (1 - SMM)^12 = 1 - {1 - smm:.6f}^12 = {1 - (1 - smm) ** 12:.2%}")

nw90 = {r["group"]: r for r in stratify_pool("region", 12, "balance_90plus")["rows"]}
nwbal = {r["group"]: r for r in stratify_pool("region", 12, "balance")["rows"]}
total90 = stratify_pool("region", 12, "balance_90plus")["total"]
print("B4  period 12: North West 90+ balance / all 90+ balance")
print(f"    = {nw90['North West']['balance_90plus']:,.2f} / {total90:,.2f} = {nw90['North West']['share_of_total']:.2%}")
print(f"    North West 90+ balance / North West balance = {nw90['North West']['balance_90plus']:,.2f} / "
      f"{nwbal['North West']['balance']:,.2f} = {nw90['North West']['ratio_within_group']:.2%}")

paid = {w["item"]: w["paid"] for w in r10["waterfall"]}
costs = {k: v for k, v in paid.items() if "fee" in k or "interest" in k}
print("B5  excess spread, period 10 = interest collections - senior fees - note interest")
print(f"    interest collections {p['interest_collections']:,.2f}")
for k, v in costs.items():
    print(f"    - {k[3:]:<20} {v:>12,.2f}")
amount = p["interest_collections"] - sum(costs.values())
print(f"    = {amount:,.2f};  annualised: 12 x {amount:,.2f} / {p['opening_balance']:,.2f} = "
      f"{12 * amount / p['opening_balance']:.2%}")
