"""Check that every file in the deal pack agrees with every other file.

Run from the repository root:

    python tests/check_deal_pack.py

The files are read as the parties send them (Excel, CSV and PDF), through the agent's readers.
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TOL = 0.05  # pounds: rounding to the penny on thousands of loans

sys.path.insert(0, str(ROOT / "python"))
from tar_agent import data as D  # noqa: E402
from tar_agent.tools.loan_tape import read_tape  # noqa: E402

terms = json.loads((DATA / "deal_terms.json").read_text())
perf = D.loan_performance()
tape_dirty = read_tape()
tape_clean = pd.read_csv(ROOT / "solutions" / "loan_tape_cutoff_clean.csv", keep_default_na=False)
issues = pd.read_csv(ROOT / "solutions" / "planted_issues.csv", keep_default_na=False)
reports = [D.investor_report(t) for t in range(1, 13)]

failures = []


def check(ok, message):
    print(("PASS  " if ok else "FAIL  ") + message)
    if not ok:
        failures.append(message)


# 1. The cut-off tape agrees with the deal terms and with period 1.
check(len(tape_clean) == terms["deal"]["n_loans"], "clean tape has 5,000 loans")
check(abs(tape_clean.current_balance.sum() - terms["initial_pool_balance"]) < TOL,
      "clean tape balance = initial pool balance")
check(abs(reports[0]["pool"]["opening_balance"] - terms["initial_pool_balance"]) < TOL,
      "period 1 opening balance = initial pool balance")
check(abs(sum(terms["initial_note_balances"].values()) - terms["initial_pool_balance"]) < TOL,
      "initial notes = initial pool balance")

# 2. Pool roll-forward in every period, and continuity between periods.
for i, r in enumerate(reports):
    p = r["pool"]
    rolled = p["opening_balance"] - p["principal_received"] - p["prepayments"] - p["defaults"]
    check(abs(rolled - p["closing_balance"]) < TOL, f"period {r['period']}: opening - principal - prepayments - defaults = closing")
    if i:
        check(abs(reports[i - 1]["pool"]["closing_balance"] - p["opening_balance"]) < TOL,
              f"period {r['period']}: opening = previous closing")

# 3. Waterfall: everything paid out comes from available funds plus reserve fund draws.
for r in reports:
    paid = sum(w["paid"] for w in r["waterfall"])
    top_up = next(w["paid"] for w in r["waterfall"] if w["item"].startswith("6."))
    check(abs(paid - (r["available_funds"] + r["reserve_fund"]["drawn"])) < TOL,
          f"period {r['period']}: waterfall pays out exactly the available funds")
    principal = next(w["paid"] for w in r["waterfall"] if w["item"].startswith("7."))
    check(abs(sum(n["principal_paid"] for n in r["notes"]) - principal) < TOL,
          f"period {r['period']}: principal split across classes adds up")
    for n in r["notes"]:
        check(abs(n["opening_balance"] - n["principal_paid"] - n["closing_balance"]) < TOL,
              f"period {r['period']}: class {n['class']} opening - principal = closing")
    check(top_up >= 0, f"period {r['period']}: reserve top-up is not negative")

# 4. Trigger values recomputed from the loan-level data match the reports.
sequential = False
for r in reports:
    p = perf[perf.period == r["period"]]
    live = p[p.status.isin(["Current", "Arrears"])]
    a90 = live[live.instalments_in_arrears >= 3].closing_balance.sum() / live.closing_balance.sum()
    cdr = perf[perf.period <= r["period"]].defaulted_balance.sum() / terms["initial_pool_balance"]
    t = r["triggers"]
    check(abs(a90 - t["arrears_90_ratio"]["value"]) < 1e-6, f"period {r['period']}: 90+ arrears ratio recomputed")
    check(abs(cdr - t["cumulative_default_ratio"]["value"]) < 1e-6, f"period {r['period']}: cumulative default ratio recomputed")
    limit = next(lim for a, b, lim in terms["triggers"]["cum_default_schedule"] if a <= r["period"] <= b)
    sequential = sequential or a90 > terms["triggers"]["arrears_90_limit"] or cdr > limit
    check(t["sequential_payment"] == sequential, f"period {r['period']}: payment mode follows the trigger rules")
    if sequential:
        juniors = sum(n["principal_paid"] for n in r["notes"] if n["class"] != "A")
        a_left = next(n["closing_balance"] for n in r["notes"] if n["class"] == "A")
        check(juniors == 0 or a_left == 0, f"period {r['period']}: sequential mode pays Class A first")

# 5. Regional servicer reports add up to the investor reports.
for r in reports:
    s = D.servicer_report(r["period"])
    check(abs(s.balance.sum() - r["pool"]["closing_balance"]) < TOL, f"period {r['period']}: servicer balance = pool balance")
    check(abs(s.balance_3_in_arrears.sum() - r["arrears"]["3_instalments"]["balance"]) < TOL,
          f"period {r['period']}: servicer 90+ balance = investor report")
    check(abs(s.defaults.sum() - r["pool"]["defaults"]) < TOL, f"period {r['period']}: servicer defaults = investor report")

# 6. The added report lines: pool factor, CPR, note factors and principal deficiency.
for r in reports:
    p = r["pool"]
    check(abs(p["pool_factor"] - p["closing_balance"] / terms["initial_pool_balance"]) < 1e-6,
          f"period {r['period']}: pool factor = closing balance / initial pool")
    smm = p["prepayments"] / (p["opening_balance"] - p["principal_received"])
    check(abs(p["cpr"] - (1 - (1 - smm) ** 12)) < 1e-6, f"period {r['period']}: CPR = 1 - (1 - SMM)^12")
    for n in r["notes"]:
        check(abs(n["factor"] - n["closing_balance"] / n["initial_balance"]) < 1e-6,
              f"period {r['period']}: class {n['class']} factor = closing / initial")
    gap = sum(n["closing_balance"] for n in r["notes"]) - p["closing_balance"]
    check(abs(r["principal_deficiency"] - max(gap, 0)) < TOL,
          f"period {r['period']}: principal deficiency = notes above the pool balance")
    principal = next(w for w in r["waterfall"] if w["item"].startswith("7."))
    check(abs(r["principal_deficiency"] - (principal["due"] - principal["paid"])) < TOL,
          f"period {r['period']}: principal deficiency = principal due - principal paid")
check(abs(reports[-1]["principal_deficiency"] - 9188.36) < 0.005, "period 12: principal deficiency is £9,188.36")

# 7. Applying the documented fixes to the received tape gives back the clean tape.
fixed = tape_dirty.drop_duplicates().copy()
for row in issues.itertuples():
    i = fixed.index[fixed.loan_id == row.loan_id][0]
    if row.column == "origination_date/maturity_date":
        o, m = row.correct_value.split("/")
        fixed.at[i, "origination_date"], fixed.at[i, "maturity_date"] = o, m
    elif row.column != "(whole row)":
        fixed.at[i, row.column] = type(tape_clean[row.column].iloc[0])(row.correct_value) \
            if row.column != "postcode_area" else row.correct_value
fixed = fixed.reset_index(drop=True).astype(tape_clean.dtypes.to_dict())
check(fixed.equals(tape_clean), "received tape + documented fixes = clean tape")
check(len(tape_dirty) - len(tape_clean) == 2, "received tape has exactly 2 duplicated rows")

# 8. The servicer report's Summary sheet carries the investor report's pool figures.
lines = {"Opening Capital Balance": "opening_balance", "Scheduled Capital Received": "principal_received",
         "Early Settlements": "prepayments", "Defaults": "defaults", "Closing Capital Balance": "closing_balance",
         "Interest Received": "interest_collections", "Recoveries": "recoveries"}
for r in reports:
    summary = D.servicer_summary(r["period"])
    check(all(abs(summary[k] - r["pool"][v]) < 0.005 for k, v in lines.items()),
          f"period {r['period']}: servicer summary = investor report pool figures")

# 9. The FCA loan-level file (AUTL) reconciles with the investor report.
for r in reports:
    fca = D.fca_loan_level(r["period"])
    live = fca[fca.AUTL70.isin(["PERF", "ARRE"])]
    check(len(live) == r["pool"]["loans_outstanding"], f"period {r['period']}: AUTL live loans = loans outstanding")
    check(abs(live.AUTL30.astype(float).sum() - r["pool"]["closing_balance"]) < TOL,
          f"period {r['period']}: AUTL current principal balance = closing pool balance")
    nd = fca.drop(columns=["AUTL1"]).isin(["ND1", "ND2", "ND3", "ND4", "ND5"]).sum().sum()
    check(len(fca.columns) == 84 and nd > 0, f"period {r['period']}: AUTL file has 84 fields and uses ND codes")

# 10. The FCA investor report (IVS) agrees with the cash manager's PDF.
for r in reports:
    ivs = D.fca_investor_report(r["period"])
    ivss = ivs["IVSS"].iloc[0]
    check(abs(float(ivss.IVSS22) / 100 - r["pool"]["cpr"]) < 5e-7, f"period {r['period']}: IVSS22 CPR = report CPR")
    status = dict(zip(ivs["IVSR"].IVSR2, ivs["IVSR"].IVSR7))
    tr = r["triggers"]
    check(status == {"CDR": "Y" if tr["cumulative_default_ratio"]["breached"] else "N",
                     "ARR90": "Y" if tr["arrears_90_ratio"]["breached"] else "N",
                     "RFREQ": "Y" if tr["reserve_fund_shortfall"]["breached"] else "N"},
          f"period {r['period']}: IVSR trigger statuses = report")
    paid = [float(x) for x in ivs["IVSF"].IVSF5]
    check(all(abs(a - w["paid"]) < 0.005 for a, w in zip(paid, r["waterfall"])) and len(paid) == len(r["waterfall"]),
          f"period {r['period']}: IVSF amounts paid = priority of payments")

print()
print(f"{len(failures)} failure(s)" if failures else "All checks passed.")
raise SystemExit(1 if failures else 0)
