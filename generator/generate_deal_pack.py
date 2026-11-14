"""Generate the deal pack for Thames Auto Receivables 2026-1 plc.

Run from the repository root:

    python generator/generate_deal_pack.py

The same seed always produces byte-identical files.
"""

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deal_terms import (BEHAVIOUR, CLASSES, DEAL, DEFINITIONS, FEES,  # noqa: E402
                        RESERVE_FUND, SEED, SONIA, TRIGGERS)
import real_files  # noqa: E402
from investor_report_pdf import write_investor_report_pdf  # noqa: E402
from investor_report_xlsx import write_investor_report_xlsx  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOLUTIONS = ROOT / "solutions"

REGIONS = {
    "London": (0.13, ["E", "N", "SE", "SW", "W"]),
    "South East": (0.15, ["GU", "RG", "BN", "ME", "OX"]),
    "South West": (0.08, ["BS", "EX", "PL", "BA"]),
    "East of England": (0.09, ["CB", "NR", "CO", "IP"]),
    "East Midlands": (0.07, ["NG", "LE", "DE"]),
    "West Midlands": (0.09, ["B", "CV", "WV", "ST"]),
    "North West": (0.11, ["M", "L", "PR", "BL", "WA"]),
    "North East": (0.04, ["NE", "SR", "DH"]),
    "Yorkshire and the Humber": (0.08, ["LS", "S", "BD", "HU"]),
    "Wales": (0.05, ["CF", "SA", "LL"]),
    "Scotland": (0.08, ["G", "EH", "AB", "DD"]),
    "Northern Ireland": (0.03, ["BT"]),
}

CUT_OFF = date.fromisoformat(DEAL["cut_off_date"])
N_PERIODS = DEAL["n_periods"]


def add_months(d, months):
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, min(d.day, 28))


def period_end(t):
    """Last day of collection period t (t = 1 is January 2026)."""
    first_next = add_months(date(CUT_OFF.year, CUT_OFF.month, 1), t + 1)
    return date.fromordinal(first_next.toordinal() - 1)


def payment_date(t):
    return add_months(date(CUT_OFF.year, CUT_OFF.month, DEAL["payment_day"]), t + 1)


def r2(x):
    return float(round(x + 0.0, 2))


# --------------------------------------------------------------------------
# 1. The loans at the cut-off date
# --------------------------------------------------------------------------

def make_loans(rng):
    n = DEAL["n_loans"]
    names = list(REGIONS)
    weights = np.array([REGIONS[r][0] for r in names])
    region = rng.choice(names, size=n, p=weights / weights.sum())
    postcode = np.array([rng.choice(REGIONS[r][1]) for r in region])

    product = rng.choice(["PCP", "HP"], size=n, p=[0.60, 0.40])
    vehicle_type = rng.choice(["New", "Used"], size=n, p=[0.40, 0.60])
    fuel = rng.choice(["Petrol", "Diesel", "Hybrid", "Electric"], size=n, p=[0.45, 0.20, 0.20, 0.15])
    value = np.where(vehicle_type == "New",
                     rng.lognormal(np.log(31000), 0.25, n),
                     rng.lognormal(np.log(15500), 0.35, n))
    value = np.clip(value, 6000, 75000).round(0)
    ltv = rng.uniform(0.75, 1.00, n)
    original = (value * ltv).round(2)

    term = np.where(product == "PCP",
                    rng.choice([36, 48], size=n, p=[0.45, 0.55]),
                    rng.choice([36, 48, 60], size=n, p=[0.30, 0.40, 0.30]))
    score = np.clip(rng.normal(780, 90, n), 450, 999).round(0).astype(int)
    apr = 8.9 + (780 - score) * 0.012 + np.where(vehicle_type == "Used", 1.0, 0.0) + rng.normal(0, 0.6, n)
    apr = np.clip(apr, 3.9, 16.9).round(2)

    balloon = np.where(product == "PCP", value * rng.uniform(0.35, 0.50, n), 0.0)
    balloon = np.minimum(balloon, original * 0.80).round(2)

    seasoning = np.array([rng.integers(3, min(t - 6, 30) + 1) for t in term])
    employment = rng.choice(["Employed", "Self-employed", "Retired", "Other"], size=n,
                            p=[0.78, 0.14, 0.06, 0.02])
    income = (rng.lognormal(np.log(38000), 0.40, n) / 100).round(0) * 100

    r = apr / 100 / 12
    pmt = (original - balloon / (1 + r) ** term) * r / (1 - (1 + r) ** -term)
    pmt = pmt.round(2)

    loans = pd.DataFrame({
        "loan_id": [f"TAR{i:05d}" for i in range(1, n + 1)],
        "origination_date": [add_months(CUT_OFF, -int(s)).replace(day=int(rng.integers(1, 29))) for s in seasoning],
        "original_term_months": term,
        "seasoning_months": seasoning,
        "product": product,
        "vehicle_type": vehicle_type,
        "fuel_type": fuel,
        "vehicle_value": value,
        "original_balance": original,
        "balloon_amount": balloon,
        "interest_rate_pct": apr,
        "monthly_instalment": pmt,
        "credit_score": score,
        "employment_status": employment,
        "annual_income": income,
        "region": region,
        "postcode_area": postcode,
    })
    loans["maturity_date"] = [add_months(d, int(t)) for d, t in zip(loans.origination_date, loans.original_term_months)]
    loans["remaining_term_months"] = loans.original_term_months - loans.seasoning_months
    loans["current_balance"] = [r2(balance_after(row, int(row.seasoning_months))) for row in loans.itertuples()]
    loans["ltv_original_pct"] = (loans.original_balance / loans.vehicle_value * 100).round(2)
    loans["days_past_due"] = 0
    return loans


def balance_after(loan, k):
    """Outstanding principal after k instalments (balloon still owed until maturity)."""
    p, b, n = loan.original_balance, loan.balloon_amount, loan.original_term_months
    r = loan.interest_rate_pct / 100 / 12
    if k >= n:
        return 0.0
    bal = p * (1 + r) ** k - loan.monthly_instalment * ((1 + r) ** k - 1) / r
    return max(bal, 0.0)


# --------------------------------------------------------------------------
# 2. Twelve months of loan performance
# --------------------------------------------------------------------------

def simulate(loans, rng):
    b = BEHAVIOUR
    smm = 1 - (1 - b["cpr"]) ** (1 / 12)
    rows = []
    defaults = []  # (period, loan_id, balance)
    for loan in loans.itertuples():
        paid = int(loan.seasoning_months)
        arrears = 0
        status = "Current"
        n = int(loan.original_term_months)
        p_miss = b["p_miss_base"] * np.exp((750 - loan.credit_score) / 120)
        for t in range(1, N_PERIODS + 1):
            if status in ("Defaulted", "Prepaid", "Repaid"):
                break
            stressed = loan.region == b["stress_region"] and t >= b["stress_from_period"]
            pm = min(p_miss * (b["stress_miss_multiplier"] if stressed else 1.0), 0.5)
            p_cure = b["stress_cure"] if stressed else b["p_cure"]
            p_stay = b["stress_stay"] if stressed else b["p_stay"]
            opening = balance_after(loan, paid)
            k = 0           # instalments paid this period
            prepay = 0.0
            u = rng.random()
            v = rng.random()
            if arrears == 0:
                if u < smm:
                    prepay = opening
                    status = "Prepaid"
                elif v < pm:
                    arrears = 1
                else:
                    k = 1
            else:
                if v < p_cure:
                    k = arrears + 1
                    arrears = 0
                elif v < p_cure + p_stay:
                    k = 1
                else:
                    arrears += 1
            k = min(k, n - paid)
            new_paid = paid + k
            opening = r2(opening)
            if new_paid < n:
                interest = k * loan.monthly_instalment - (balance_after(loan, paid) - balance_after(loan, new_paid))
            else:
                interest = k * loan.monthly_instalment - (balance_after(loan, paid) - loan.balloon_amount)
            paid = new_paid
            # Work in pence: principal is the change in the rounded balance, so every line ties exactly.
            closing = 0.0 if (status == "Prepaid" or paid >= n) else r2(balance_after(loan, paid))
            if status == "Prepaid":
                prepay, sched_principal = opening, 0.0
            else:
                sched_principal = r2(opening - closing)
            default_bal = 0.0
            if arrears >= 4:
                status = "Defaulted"
                default_bal = closing
                defaults.append((t, loan.loan_id, default_bal))
                closing = 0.0
            elif status != "Prepaid":
                if paid >= n:
                    status = "Repaid"
                else:
                    status = "Current" if arrears == 0 else "Arrears"
            rows.append({
                "loan_id": loan.loan_id, "period": t,
                "period_end": period_end(t).isoformat(),
                "opening_balance": r2(opening),
                "instalments_paid": k,
                "principal_paid": r2(sched_principal),
                "interest_paid": r2(max(interest, 0.0)),
                "prepayment": r2(prepay),
                "defaulted_balance": r2(default_bal),
                "closing_balance": r2(closing),
                "instalments_in_arrears": arrears if status != "Defaulted" else 4,
                "status": status,
            })
    perf = pd.DataFrame(rows)
    rec = {}
    lag, rate = DEFINITIONS["recovery_lag"], DEFINITIONS["recovery_rate"]
    for t, lid, bal in defaults:
        if t + lag <= N_PERIODS:
            rec.setdefault(t + lag, []).append((lid, r2(bal * rate)))
    return perf, rec


# --------------------------------------------------------------------------
# 3. Pool figures, waterfall and trigger tests for each period
# --------------------------------------------------------------------------

def run_waterfall(loans, perf, recoveries):
    initial_pool = r2(loans.current_balance.sum())
    notes = {}
    allocated = 0.0
    for c in CLASSES[1:]:
        notes[c["name"]] = r2(initial_pool * c["share"])
        allocated += notes[c["name"]]
    notes["A"] = r2(initial_pool - allocated)
    notes = {c["name"]: notes[c["name"]] for c in CLASSES}
    initial_notes = dict(notes)
    rf_required = r2(sum(initial_notes.values()) * RESERVE_FUND["required_pct_of_initial_notes"])
    reserve = rf_required
    sequential = False
    cum_default = 0.0
    cum_recovery = 0.0
    reports = []
    for t in range(1, N_PERIODS + 1):
        p = perf[perf.period == t]
        pool_open = r2(p.opening_balance.sum())
        sched = r2(p.principal_paid.sum())
        prepay = r2(p.prepayment.sum())
        interest = r2(p.interest_paid.sum())
        dflt = r2(p.defaulted_balance.sum())
        rec = r2(sum(a for _, a in recoveries.get(t, [])))
        pool_close = r2(p.closing_balance.sum())
        cum_default = r2(cum_default + dflt)
        cum_recovery = r2(cum_recovery + rec)

        live = p[p.status.isin(["Current", "Arrears"])]
        buckets = {}
        for k in range(0, 4):
            sel = live[live.instalments_in_arrears == k]
            buckets[k] = {"count": int(len(sel)), "balance": r2(sel.closing_balance.sum())}
        arrears90 = r2(sum(buckets[k]["balance"] for k in (3,)))
        arrears90_ratio = arrears90 / pool_close if pool_close else 0.0
        cdr = cum_default / initial_pool
        cum_default_limit = next(lim for a, b, lim in TRIGGERS["cum_default_schedule"] if a <= t <= b)

        # Trigger tests are run on the period-end figures, before the payment date.
        breach_cdr = cdr > cum_default_limit
        breach_90 = arrears90_ratio > TRIGGERS["arrears_90_limit"]
        breach_rf_prev = reserve < rf_required - 0.005
        newly = (breach_cdr or breach_90 or breach_rf_prev) and not sequential
        sequential = sequential or breach_cdr or breach_90 or breach_rf_prev

        available = r2(interest + sched + prepay + rec)
        lines = []
        rf_draw = 0.0

        def pay(label, due):
            nonlocal available, reserve, rf_draw
            due = r2(due)
            from_avail = min(due, available)
            available = r2(available - from_avail)
            short = r2(due - from_avail)
            draw = min(short, reserve)
            reserve = r2(reserve - draw)
            rf_draw = r2(rf_draw + draw)
            paid_amt = r2(from_avail + draw)
            lines.append({"item": label, "due": due, "paid": paid_amt})
            return paid_amt

        pay("1. Servicer fee", pool_open * FEES["servicer_fee_rate"] / 12)
        pay("1. Trustee fee", FEES["trustee_fee_monthly"])
        class_interest = {}
        for c in CLASSES:
            rate = SONIA[t - 1] + c["margin"]
            class_interest[c["name"]] = pay(f"{1 + CLASSES.index(c) + 1}. Class {c['name']} interest",
                                            notes[c["name"]] * rate / 12)
        top_up = min(r2(rf_required - reserve), available)
        available = r2(available - top_up)
        reserve = r2(reserve + top_up)
        lines.append({"item": "6. Reserve fund top-up", "due": r2(top_up), "paid": r2(top_up)})

        notes_open = dict(notes)
        principal_due = r2(max(sum(notes.values()) - pool_close, 0.0))
        principal_paid = r2(min(principal_due, available))
        available = r2(available - principal_paid)
        alloc = {}
        if sequential:
            left = principal_paid
            for c in CLASSES:
                x = r2(min(left, notes[c["name"]]))
                alloc[c["name"]] = x
                left = r2(left - x)
        else:
            total = sum(notes.values())
            running = 0.0
            for c in CLASSES[1:]:
                x = r2(principal_paid * notes[c["name"]] / total)
                alloc[c["name"]] = x
                running += x
            alloc["A"] = r2(principal_paid - running)
        for name in notes:
            notes[name] = r2(notes[name] - alloc[name])
        lines.append({"item": "7. Principal on the notes", "due": principal_due, "paid": principal_paid})
        lines.append({"item": "8. Deferred consideration to the originator", "due": r2(available), "paid": r2(available)})
        residual = available

        reports.append({
            "deal": DEAL["issuer"],
            "period": t,
            "collection_period_end": period_end(t).isoformat(),
            "payment_date": payment_date(t).isoformat(),
            "sonia": SONIA[t - 1],
            "pool": {
                "loans_outstanding": int(len(live)),
                "opening_balance": pool_open,
                "principal_received": sched,
                "prepayments": prepay,
                "defaults": dflt,
                "closing_balance": pool_close,
                "interest_collections": interest,
                "recoveries": rec,
                "cumulative_defaults": cum_default,
                "cumulative_recoveries": cum_recovery,
                # Added for realism: share of the initial pool still outstanding, and the period's
                # prepayment speed as an annual rate (CPR = 1 - (1 - SMM)^12, SMM = prepayments /
                # (opening balance - principal received from instalments)).
                "pool_factor": round(pool_close / initial_pool, 6),
                "cpr": round(1 - (1 - prepay / (pool_open - sched)) ** 12, 6),
            },
            "arrears": {f"{k}_instalments": buckets[k] for k in range(4)},
            "available_funds": r2(interest + sched + prepay + rec),
            "waterfall": lines,
            "reserve_fund": {"required": rf_required, "drawn": rf_draw, "balance": reserve},
            "notes": [{
                "class": c["name"], "rating": c["rating"],
                "margin": c["margin"], "coupon": round(SONIA[t - 1] + c["margin"], 6),
                "opening_balance": notes_open[c["name"]],
                "interest_paid": class_interest[c["name"]],
                "principal_paid": alloc[c["name"]],
                "closing_balance": notes[c["name"]],
                "initial_balance": initial_notes[c["name"]],
                "factor": round(notes[c["name"]] / initial_notes[c["name"]], 6),
            } for c in CLASSES],
            # Notes outstanding above the pool balance after the payment date (0 when fully collateralised).
            "principal_deficiency": r2(max(sum(notes.values()) - pool_close, 0.0)),
            "triggers": {
                "cumulative_default_ratio": {"value": round(cdr, 6), "limit": cum_default_limit, "breached": bool(breach_cdr)},
                "arrears_90_ratio": {"value": round(arrears90_ratio, 6), "limit": TRIGGERS["arrears_90_limit"],
                                     "breached": bool(breach_90)},
                "reserve_fund_shortfall": {"breached": bool(breach_rf_prev)},
                "sequential_payment": bool(sequential),
                "newly_breached_this_period": bool(newly),
            },
            "residual_to_originator": r2(residual),
        })
    return initial_pool, initial_notes, rf_required, reports


# --------------------------------------------------------------------------
# 4. Planted data-quality issues in the cut-off loan tape
# --------------------------------------------------------------------------

TAPE_COLUMNS = ["loan_id", "origination_date", "maturity_date", "original_term_months",
                "remaining_term_months", "product", "vehicle_type", "fuel_type", "vehicle_value",
                "original_balance", "current_balance", "balloon_amount", "ltv_original_pct",
                "interest_rate_pct", "monthly_instalment", "credit_score", "employment_status",
                "annual_income", "region", "postcode_area", "days_past_due"]


def plant_issues(clean, rng):
    dirty = clean.copy()
    ids = list(rng.choice(dirty.index, size=9, replace=False))
    issues = []

    def note(i, column, problem, fix, received, correct):
        issues.append({"loan_id": dirty.at[i, "loan_id"], "column": column, "problem": problem,
                       "fix": fix, "value_received": received, "correct_value": correct})

    i = ids[0]; old = dirty.at[i, "interest_rate_pct"]
    dirty.at[i, "interest_rate_pct"] = round(old * 100, 0)
    note(i, "interest_rate_pct", "rate entered without the decimal point", "divide by 100",
         dirty.at[i, "interest_rate_pct"], old)
    i = ids[1]; old = dirty.at[i, "current_balance"]
    dirty.at[i, "current_balance"] = -old
    note(i, "current_balance", "negative balance (sign error)", "take the absolute value", -old, old)
    i = ids[2]; old = dirty.at[i, "region"]
    dirty.at[i, "region"] = "Nort West" if old == "North West" else old.lower()
    note(i, "region", "region name misspelt or wrong case", "map to the standard region name",
         dirty.at[i, "region"], old)
    for i in ids[3:5]:
        old = dirty.at[i, "postcode_area"]
        dirty.at[i, "postcode_area"] = ""
        note(i, "postcode_area", "missing postcode area", "leave missing and flag; region is still known", "", old)
    i = ids[5]; old_o, old_m = dirty.at[i, "origination_date"], dirty.at[i, "maturity_date"]
    dirty.at[i, "origination_date"], dirty.at[i, "maturity_date"] = old_m, old_o
    note(i, "origination_date/maturity_date", "origination and maturity dates swapped", "swap them back",
         f"{old_m}/{old_o}", f"{old_o}/{old_m}")
    i = ids[6]; old = dirty.at[i, "credit_score"]
    dirty.at[i, "credit_score"] = 9999
    note(i, "credit_score", "credit score outside the 0-999 scale (placeholder value)",
         "treat as missing and flag", 9999, old)
    dup_rows = dirty.loc[ids[7:9]]
    for i in ids[7:9]:
        issues.append({"loan_id": dirty.at[i, "loan_id"], "column": "(whole row)",
                       "problem": "row duplicated", "fix": "drop the second copy",
                       "value_received": "2 rows", "correct_value": "1 row"})
    dirty = pd.concat([dirty, dup_rows]).sort_values("loan_id", kind="stable").reset_index(drop=True)
    return dirty, pd.DataFrame(issues)


# --------------------------------------------------------------------------
# 5. Write everything
# --------------------------------------------------------------------------

def money(x):
    return f"£{x:,.2f}"


def write_investor_report_md(rep, path):
    p, a, rf, tr = rep["pool"], rep["arrears"], rep["reserve_fund"], rep["triggers"]
    L = [f"# {rep['deal']}", "", f"## Investor report — collection period {rep['period']}",
         "", f"Collection period ending: {rep['collection_period_end']}  ",
         f"Payment date: {rep['payment_date']}  ", f"SONIA for the period: {rep['sonia']:.2%}", "",
         "## Pool performance", "", "| Item | Amount |", "|---|---:|"]
    for label, key in [("Opening pool balance", "opening_balance"), ("Principal received from instalments", "principal_received"),
                       ("Prepayments", "prepayments"), ("Defaults", "defaults"),
                       ("Closing pool balance", "closing_balance"), ("Interest collections", "interest_collections"),
                       ("Recoveries", "recoveries"), ("Cumulative defaults", "cumulative_defaults"),
                       ("Cumulative recoveries", "cumulative_recoveries")]:
        L.append(f"| {label} | {money(p[key])} |")
    L += ["", f"Loans outstanding: {p['loans_outstanding']:,}  ", f"Pool factor: {p['pool_factor']:.4f}  ",
          f"CPR (annualised, this period): {p['cpr']:.2%}", "", "## Arrears", "",
          "| Instalments in arrears | Loans | Balance |", "|---|---:|---:|"]
    for k in range(4):
        b = a[f"{k}_instalments"]
        label = f"{k}" if k < 3 else "3 (90+ days)"
        L.append(f"| {label} | {b['count']:,} | {money(b['balance'])} |")
    L += ["", "## Priority of payments", "", f"Available funds: {money(rep['available_funds'])}", "",
          "| Item | Due | Paid |", "|---|---:|---:|"]
    for w in rep["waterfall"]:
        L.append(f"| {w['item']} | {money(w['due'])} | {money(w['paid'])} |")
    L += ["", "## Notes", "",
          "| Class | Rating | Coupon | Opening | Interest | Principal | Closing | Factor |",
          "|---|---|---:|---:|---:|---:|---:|---:|"]
    for n in rep["notes"]:
        L.append(f"| {n['class']} | {n['rating']} | {n['coupon']:.2%} | {money(n['opening_balance'])} | "
                 f"{money(n['interest_paid'])} | {money(n['principal_paid'])} | {money(n['closing_balance'])} | "
                 f"{n['factor']:.4f} |")
    L += ["", f"Principal deficiency after the payment date: {money(rep['principal_deficiency'])}"]
    L += ["", "## Reserve fund", "",
          f"Required amount: {money(rf['required'])}  ", f"Drawn this period: {money(rf['drawn'])}  ",
          f"Balance after the payment date: {money(rf['balance'])}", "", "## Trigger tests", "",
          "| Test | Value | Limit | Result |", "|---|---:|---:|---|"]
    c, r9 = tr["cumulative_default_ratio"], tr["arrears_90_ratio"]
    L.append(f"| Cumulative default ratio | {c['value']:.2%} | {c['limit']:.2%} | {'BREACHED' if c['breached'] else 'Pass'} |")
    L.append(f"| 90+ day arrears ratio | {r9['value']:.2%} | {r9['limit']:.2%} | {'BREACHED' if r9['breached'] else 'Pass'} |")
    L.append(f"| Reserve fund at required amount | — | — | {'BREACHED' if tr['reserve_fund_shortfall']['breached'] else 'Pass'} |")
    L += ["", f"Principal is paid {'sequentially (Class A first)' if tr['sequential_payment'] else 'pro rata across all classes'} "
          "on this payment date.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


def write_servicer_report(perf, loans, t, path):
    """One row per region: live loans, balance by arrears bucket, defaults and prepayments."""
    p = perf[perf.period == t].merge(loans[["loan_id", "region"]], on="loan_id")
    live = p[p.status.isin(["Current", "Arrears"])]
    rows = []
    for region in REGIONS:
        lr, pr = live[live.region == region], p[p.region == region]
        rows.append({
            "period": t, "region": region, "loans_outstanding": int(len(lr)),
            "balance": r2(lr.closing_balance.sum()),
            **{f"balance_{k}_in_arrears": r2(lr[lr.instalments_in_arrears == k].closing_balance.sum()) for k in (1, 2, 3)},
            "defaults": r2(pr.defaulted_balance.sum()),
            "prepayments": r2(pr.prepayment.sum()),
        })
    table = pd.DataFrame(rows)
    table.to_csv(path, index=False)
    return table


def main():
    rng = np.random.default_rng(SEED)
    loans = make_loans(rng)
    perf, recoveries = simulate(loans, rng)
    initial_pool, initial_notes, rf_required, reports = run_waterfall(loans, perf, recoveries)

    for d in [DATA / "investor_reports", DATA / "servicer_reports", SOLUTIONS]:
        d.mkdir(parents=True, exist_ok=True)

    clean = loans[TAPE_COLUMNS].copy()
    clean["origination_date"] = clean.origination_date.astype(str)
    clean["maturity_date"] = clean.maturity_date.astype(str)
    dirty, issues = plant_issues(clean, rng)
    dirty.to_csv(DATA / "loan_tape_cutoff.csv", index=False)
    clean.to_csv(SOLUTIONS / "loan_tape_cutoff_clean.csv", index=False)
    issues.to_csv(SOLUTIONS / "planted_issues.csv", index=False)

    perf.to_csv(DATA / "loan_performance.csv", index=False)

    snap = loans[["loan_id", "product", "vehicle_type", "fuel_type", "original_balance", "interest_rate_pct",
                  "credit_score", "region", "postcode_area", "maturity_date"]].copy()
    snap["maturity_date"] = snap.maturity_date.astype(str)
    status = perf.groupby("loan_id").tail(1).set_index("loan_id")
    snap["status"] = snap.loan_id.map(status.status)
    snap["current_balance"] = snap.loan_id.map(status.closing_balance)
    snap["instalments_in_arrears"] = snap.loan_id.map(status.instalments_in_arrears)
    snap["status_period"] = snap.loan_id.map(status.period)
    snap.to_csv(DATA / "loan_tape_2026_12.csv", index=False)

    regional = {}
    for rep in reports:
        stem = f"investor_report_{period_end(rep['period']).strftime('%Y_%m')}"
        (DATA / "investor_reports" / f"{stem}.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
        write_investor_report_md(rep, DATA / "investor_reports" / f"{stem}.md")
        regional[rep["period"]] = write_servicer_report(perf, loans, rep["period"],
                              DATA / "servicer_reports" / f"servicer_report_{period_end(rep['period']).strftime('%Y_%m')}.csv")

    terms = {"deal": DEAL, "classes": CLASSES, "sonia": SONIA, "fees": FEES, "reserve_fund": RESERVE_FUND,
             "triggers": {**TRIGGERS, "cum_default_schedule": [list(x) for x in TRIGGERS["cum_default_schedule"]]},
             "definitions": DEFINITIONS, "initial_pool_balance": initial_pool,
             "initial_note_balances": initial_notes, "reserve_fund_required_amount": rf_required}
    (DATA / "deal_terms.json").write_text(json.dumps(terms, indent=2), encoding="utf-8")

    # The same deal in the formats the parties really send (Kestrel's Excel files, Larkmead's PDF reports and
    # the FCA loan-level files): see real_files.py.
    real_files.write_all(DATA, loans, perf, recoveries, reports, dirty, regional, DEAL,
                         write_investor_report_pdf, write_investor_report_xlsx)

    for rep in reports:
        tr = rep["triggers"]
        print(rep["period"], rep["pool"]["closing_balance"],
              f"cdr={tr['cumulative_default_ratio']['value']:.4%}",
              f"90+={tr['arrears_90_ratio']['value']:.4%}",
              "SEQ" if tr["sequential_payment"] else "pro rata",
              f"rf={rep['reserve_fund']['balance']}", f"res={rep['residual_to_originator']}")


if __name__ == "__main__":
    main()
