import calendar
"""Build the Thames prospectus (PDF) from the deal terms and the clean cut-off tape.

The key sections below are the ones the agent reads; prospectus_long.py places them, renumbered, among
the longer sections of a full prospectus (generator/prospectus_text/thames/).

Run from the repository root after generate_deal_pack.py:

    python generator/build_prospectus.py

Needs pandoc and XeLaTeX.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "prospectus"

terms = json.loads((DATA / "deal_terms.json").read_text())
tape = pd.read_csv(ROOT / "solutions" / "loan_tape_cutoff_clean.csv")
d, fees, trig = terms["deal"], terms["fees"], terms["triggers"]
pool = terms["initial_pool_balance"]


def money(x):
    return f"£{x:,.2f}"


def pct(x, dp=2):
    return f"{x * 100:.{dp}f}%"


def wavg(col):
    return (tape[col] * tape.current_balance).sum() / tape.current_balance.sum()


def strat(series, title, order=None):
    g = tape.groupby(series, observed=True).agg(loans=("loan_id", "count"), balance=("current_balance", "sum"))
    if order is not None:
        g = g.reindex([o for o in order if o in g.index])
    lines = [f"**{title}**", "", "| Category | Loans | Balance | Share of balance |", "|---|---:|---:|---:|"]
    for k, r in g.iterrows():
        lines.append(f"| {k} | {int(r.loans):,} | {money(r.balance)} | {pct(r.balance / pool)} |")
    lines.append(f"| **Total** | **{int(g.loans.sum()):,}** | **{money(g.balance.sum())}** | **100.00%** |")
    return "\n".join(lines) + "\n"


tape["score_band"] = pd.cut(tape.credit_score, [0, 649, 699, 749, 799, 849, 999],
                            labels=["Below 650", "650–699", "700–749", "750–799", "800–849", "850 and above"])
tape["rate_band"] = pd.cut(tape.interest_rate_pct, [0, 7.99, 8.99, 9.99, 10.99, 99],
                           labels=["Below 8.00%", "8.00–8.99%", "9.00–9.99%", "10.00–10.99%", "11.00% and above"])
tape["ltv_band"] = pd.cut(tape.ltv_original_pct, [0, 79.99, 84.99, 89.99, 94.99, 100],
                          labels=["Below 80%", "80–84.99%", "85–89.99%", "90–94.99%", "95–100%"])
tape["term_band"] = pd.cut(tape.remaining_term_months, [0, 12, 24, 36, 60],
                           labels=["1–12 months", "13–24 months", "25–36 months", "37–60 months"])

notes_rows = "\n".join(
    f"| Class {c['name']} | {money(terms['initial_note_balances'][c['name']])} | {pct(c['share'], 0)} | "
    f"SONIA + {pct(c['margin'])} | {c['rating']} |" for c in terms["classes"])
cdr_rows = "\n".join(f"| Periods {a} to {b} | {pct(lim)} |" for a, b, lim in trig["cum_default_schedule"])
seasoning = (tape.original_term_months - tape.remaining_term_months)

md = f"""---
title: "{d['issuer']}"
subtitle: "Prospectus (short form) — £{pool:,.2f} asset-backed floating rate notes"
date: "{d['closing_date']}"
geometry: "a4paper, margin=2.5cm"
mainfont: "TeX Gyre Pagella"
sansfont: "TeX Gyre Heros"
monofont: "DejaVu Sans Mono"
fontsize: 11pt
header-includes:
  - \\usepackage{{fancyhdr}}
  - \\pagestyle{{fancy}}
  - \\fancyhf{{}}
  - \\fancyhead[L]{{\\small {d['issuer']}}}
  - \\fancyhead[R]{{\\small Prospectus}}
  - \\fancyfoot[C]{{\\small Page \\thepage}}
  - \\fancypagestyle{{plain}}{{\\fancyhf{{}}\\fancyfoot[C]{{\\small Page \\thepage}}\\renewcommand{{\\headrulewidth}}{{0pt}}}}
---

# Important notice

This document is a teaching prospectus written for the book *Learning AI from Zero — Build Your Own AI Agent*.
The issuer, the originator, the trustee and every loan in the portfolio are fictional. Any resemblance to a
real company or person is a coincidence. Real prospectuses run to several hundred pages; this one keeps only
the sections an analyst needs to monitor the deal: the parties, the notes, the portfolio, the priority of
payments, the reserve fund and the trigger events.

Throughout this document, "period" means a monthly collection period. Period 1 is January 2026 and period 12 is
December 2026. Each period is followed by a payment date on the {d['payment_day']}th day of the next month.

\\newpage

# 1. Transaction overview

| Item | Detail |
|---|---|
| Issuer | {d['issuer']} |
| Originator and seller | {d['originator']} |
| Servicer | {d['servicer']} |
| Trustee | {d['trustee']} |
| Assets | UK motor vehicle loans: hire purchase (HP) and personal contract purchase (PCP) |
| Number of loans at the cut-off date | {len(tape):,} |
| Pool balance at the cut-off date | {money(pool)} |
| Cut-off date | {d['cut_off_date']} |
| Closing date | {d['closing_date']} |
| First payment date | {d['first_payment_date']} |
| Payment frequency | Monthly, on the {d['payment_day']}th day of each month |
| Currency | Pounds sterling (GBP) |
| Risk retention | The originator retains 5% of the nominal value of each class of notes (a vertical slice) |

The issuer buys the loans from the originator on the closing date and pays for them with the proceeds of
the notes. The borrowers keep paying their monthly instalments to the servicer, which passes the money to the
issuer. The issuer uses that money, on each payment date, to pay its fees, the interest on the notes and the
principal on the notes, in the order set out in section 5.

**Risk retention.** UK securitisation rules require the originator to keep a material net economic interest of
at least 5% in the transaction. The originator holds it as a *vertical slice*: 5% of the nominal value of each
class of notes, kept for the life of the transaction and not hedged or sold. Holding Class D alone would not be
enough, because Class D is 4% of the notes.

\\newpage

# 2. The notes

The table shows the margin of each class of notes over SONIA and its rating at closing.

| Class | Initial balance | Share | SONIA + margin | Rating |
|---|---:|---:|---|---|
{notes_rows}

**Interest.** Each class pays interest monthly at SONIA plus its margin. For each period, interest equals the
class balance at the start of the period multiplied by one-twelfth of the annual rate. The SONIA rate for each
period is stated in the investor report.

**Principal.** On each payment date the issuer pays principal so that the total balance of the notes falls to
the pool balance at the end of the period, provided enough funds are available (section 5, item 7).

**Pro rata and sequential payment.** Until a trigger event occurs (section 6), principal is shared between all
classes in proportion to their balances (*pro rata*). From the first payment date on which a trigger event has
occurred, principal is paid *sequentially*: Class A is repaid in full before Class B receives any principal,
then Class B before Class C, then Class C before Class D. The switch to sequential payment is permanent.

\\newpage

# 3. The portfolio at the cut-off date

| Characteristic | Value |
|---|---:|
| Number of loans | {len(tape):,} |
| Pool balance | {money(pool)} |
| Average current balance | {money(tape.current_balance.mean())} |
| Largest current balance | {money(tape.current_balance.max())} |
| Weighted average interest rate | {wavg('interest_rate_pct'):.2f}% |
| Weighted average remaining term | {wavg('remaining_term_months'):.1f} months |
| Weighted average seasoning | {(seasoning * tape.current_balance).sum() / pool:.1f} months |
| Weighted average credit score | {wavg('credit_score'):.0f} |
| Weighted average original loan-to-value | {wavg('ltv_original_pct'):.2f}% |
| Share of PCP loans (by balance) | {pct(tape[tape['product'] == 'PCP'].current_balance.sum() / pool)} |
| Total balloon amounts (PCP) | {money(tape.balloon_amount.sum())} |

{strat('region', 'Table 3.1 — Distribution by region')}

\\newpage

{strat('product', 'Table 3.2 — Distribution by product')}

{strat('vehicle_type', 'Table 3.3 — Distribution by vehicle type')}

{strat('fuel_type', 'Table 3.4 — Distribution by fuel type', ['Petrol', 'Diesel', 'Hybrid', 'Electric'])}

{strat('score_band', 'Table 3.5 — Distribution by credit score')}

\\newpage

{strat('rate_band', 'Table 3.6 — Distribution by interest rate')}

{strat('ltv_band', 'Table 3.7 — Distribution by original loan-to-value')}

{strat('term_band', 'Table 3.8 — Distribution by remaining term')}

\\newpage

# 4. Eligibility criteria and definitions

Each loan met the following criteria at the cut-off date:

1. The borrower is an individual resident in the United Kingdom.
2. The loan is a hire purchase or personal contract purchase agreement for a car.
3. No instalment was in arrears (days past due equal to 0).
4. At least 3 instalments had been paid (seasoning of 3 months or more).
5. At least 6 instalments remained to be paid.
6. The original loan-to-value was 100% or less.

**Definitions used in this prospectus**

- **Pool balance**: {terms['definitions']['pool_balance']}
- **Defaulted loan**: {terms['definitions']['default']} A defaulted loan leaves the pool balance in the period
  in which it defaults; its outstanding principal at that date is its *defaulted balance*.
- **Recoveries**: amounts received after a default, mainly from the sale of the vehicle. For this transaction
  the servicer expects to recover {pct(terms['definitions']['recovery_rate'], 0)} of the defaulted balance,
  {terms['definitions']['recovery_lag']} periods after the default.
- **Cumulative default ratio**: the sum of the defaulted balances of all loans that have defaulted since the
  cut-off date, divided by the pool balance at the cut-off date ({money(pool)}).
- **90+ day arrears ratio**: the total balance of loans that are not defaulted and have 3 instalments in
  arrears, divided by the pool balance, both measured at the end of the period.
- **Available funds**: for each period, the sum of interest collections, principal received from instalments
  (including balloon payments), prepayments and recoveries received during the period.

\\newpage

# 5. Priority of payments

On each payment date the issuer applies the available funds in the following order. An item is paid only
when every item above it has been paid in full.

1. **Senior fees**: the servicer fee of {pct(fees['servicer_fee_rate'])} per year on the pool balance at the
   start of the period (paid monthly at one-twelfth of that rate), and the trustee fee of
   {money(fees['trustee_fee_monthly'])} per payment date.
2. **Class A interest.**
3. **Class B interest.**
4. **Class C interest.**
5. **Class D interest.**
6. **Reserve fund top-up**: the amount needed to bring the reserve fund back to its required amount.
7. **Principal on the notes**: the amount needed to reduce the total note balance to the pool balance at the
   end of the period, paid pro rata or sequentially as described in section 2.
8. **Deferred consideration**: any remaining amount is paid to the originator.

If the available funds are not enough to pay items 1 to 5 in full, the shortfall is drawn from the reserve
fund. The reserve fund is never used to pay principal or deferred consideration.

If the funds left for item 7 are lower than the amount needed, the total note balance stays above the pool
balance. The difference is called a *principal deficiency*; it is reduced on later payment dates from the
funds left after item 6.

\\newpage

# 6. Reserve fund and trigger events

**Reserve fund.** On the closing date the originator funds a reserve fund of
{money(terms['reserve_fund_required_amount'])}, equal to
{pct(terms['reserve_fund']['required_pct_of_initial_notes'])} of the initial balance of the notes. The
required amount stays at this level for the life of the transaction.

**Trigger events.** A trigger event occurs when any of the following tests fails. The tests use the figures at
the end of each period and are reported in each investor report.

*Test 1 — Cumulative default ratio.* The cumulative default ratio must not exceed:

| Periods | Maximum cumulative default ratio |
|---|---:|
{cdr_rows}

*Test 2 — 90+ day arrears ratio.* The 90+ day arrears ratio must not exceed {pct(trig['arrears_90_limit'])}.

*Test 3 — Reserve fund.* After the previous payment date, the reserve fund must be at its required amount.

**Consequence.** From the payment date that follows the period in which a trigger event occurs, principal is
paid sequentially (section 2). The switch is permanent, even if the test is passed again in a later period.

**Reporting.** Within 15 days after each payment date, the servicer publishes an investor report showing the
pool performance, the arrears, the application of funds, the note balances, the reserve fund and the result
of each test in this section.
"""

# ---------------------------------------------------------------- the full-length document

import sys  # noqa: E402
from datetime import date  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prospectus_long as L  # noqa: E402

FINAL_MATURITY = "2032-12-20"
def _words(iso):
    y, m, dd = map(int, str(iso).split("-"))
    return f"{dd} {calendar.month_name[m]} {y}"


VALUES = {"issuer": d["issuer"], "originator": d["originator"], "closing_date": _words(d["closing_date"]),
          "cut_off_date": _words(d["cut_off_date"]), "first_payment_date": _words(d["first_payment_date"]),
          "payment_day": f"{d['payment_day']}th", "final_maturity_date": _words(FINAL_MATURITY),
          "pool_balance": money(pool), "n_loans": f"{len(tape):,}",
          "servicer_fee": f"{terms['fees']['servicer_fee_rate'] * 100:.2f}%"}

# Extra stratification tables of section 10 (the first eight keep their numbers 3.1 to 3.8 -> 10.1 to 10.8).
tape["orig_year"] = tape.origination_date.str[:4]
tape["seasoning_band"] = pd.cut(seasoning, [0, 6, 12, 24, 36, 120],
                                labels=["3–6 months", "7–12 months", "13–24 months", "25–36 months", "Over 36 months"])
tape["balance_band"] = pd.cut(tape.current_balance, [0, 5000, 10000, 15000, 20000, 30000, 1e9],
                              labels=["Up to £5,000", "£5,000.01–£10,000", "£10,000.01–£15,000",
                                      "£15,000.01–£20,000", "£20,000.01–£30,000", "Over £30,000"])
tape["orig_term_band"] = pd.cut(tape.original_term_months, [0, 24, 36, 48, 60, 999],
                                labels=["Up to 24 months", "25–36 months", "37–48 months", "49–60 months", "Over 60 months"])
tape["income_band"] = pd.cut(tape.annual_income, [0, 20000, 30000, 40000, 60000, 1e9],
                             labels=["Up to £20,000", "£20,000.01–£30,000", "£30,000.01–£40,000",
                                     "£40,000.01–£60,000", "Over £60,000"])
tape["maturity_year"] = tape.maturity_date.str[:4]
pcp = tape["product"] == "PCP"
tape["balloon_share"] = np.where(pcp, tape.balloon_amount / tape.current_balance, np.nan)
tape["balloon_band"] = pd.cut(tape.balloon_share, [0, 0.25, 0.5, 0.75, 1.0, 99],
                              labels=["Up to 25%", "25–50%", "50–75%", "75–100%", "Over 100%"])
extra_tables = [
    strat("orig_year", "Table 10.9 — Distribution by year of origination"),
    strat("seasoning_band", "Table 10.10 — Distribution by seasoning"),
    strat("balance_band", "Table 10.11 — Distribution by current balance"),
    strat("orig_term_band", "Table 10.12 — Distribution by original term"),
    strat("maturity_year", "Table 10.13 — Distribution by year of maturity"),
    strat("employment_status", "Table 10.14 — Distribution by employment status of the borrower"),
    strat("income_band", "Table 10.15 — Distribution by annual income of the borrower"),
    strat("postcode_area", "Table 10.16 — Distribution by postcode area"),
]
pcp_tape = tape[pcp]
g = pcp_tape.groupby("balloon_band", observed=True).agg(loans=("loan_id", "count"), balance=("current_balance", "sum"),
                                                        balloon=("balloon_amount", "sum"))
rows = ["**Table 10.17 — PCP loans: balloon payment as a share of current balance**", "",
        "| Balloon / current balance | Loans | Current balance | Balloon payments |", "|---|---:|---:|---:|"]
for k, r in g.iterrows():
    rows.append(f"| {k} | {int(r.loans):,} | {money(r.balance)} | {money(r.balloon)} |")
rows.append(f"| **Total** | **{int(g.loans.sum()):,}** | **{money(g.balance.sum())}** | **{money(g.balloon.sum())}** |")
extra_tables.append("\n".join(rows) + "\n")


# Weighted average lives (section 17): scheduled amortisation of every loan, a constant prepayment rate,
# no defaults, principal paid pro rata, with and without the clean-up call.
def pool_principal(cpr):
    bal = tape.current_balance.to_numpy(dtype=float).copy()
    r = tape.interest_rate_pct.to_numpy(dtype=float) / 1200
    inst = tape.monthly_instalment.to_numpy(dtype=float)
    n = tape.remaining_term_months.to_numpy(dtype=int)
    balloon = tape.balloon_amount.to_numpy(dtype=float)
    smm = 1 - (1 - cpr) ** (1 / 12)
    flows = []
    for m in range(1, n.max() + 1):
        live = (n >= m) & (bal > 0.005)
        sched = np.where(live, np.minimum(bal, np.maximum(inst - bal * r, 0)), 0)
        last = live & (n == m)
        sched = np.where(last, bal, sched)                      # the last instalment repays the rest (balloon)
        bal = bal - sched
        prep = np.where(live & ~last, bal * smm, 0)
        bal = bal - prep
        flows.append(sched.sum() + prep.sum())
    return np.array(flows)


def wal_row(cpr, call):
    flows = pool_principal(cpr)
    remaining = pool - np.cumsum(flows)
    if call:
        k = int(np.argmax(remaining < 0.10 * pool))
        flows = flows[: k + 1].copy()
        flows[k] += max(remaining[k], 0)
    months = np.arange(1, len(flows) + 1)
    wal = (months * flows).sum() / flows.sum() / 12
    last = len(flows)
    y, mth = 2026 + (last) // 12, (last) % 12 + 1
    return wal, date(y if mth != 12 else y, mth, 20).strftime("%B %Y")


wal_lines = ["| Constant prepayment rate | Weighted average life (years), with clean-up call | Last payment date, "
             "with call | Weighted average life (years), to maturity | Last payment date, to maturity |",
             "|---:|---:|---|---:|---|"]
for cpr in (0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
    w1, d1 = wal_row(cpr, True)
    w2, d2 = wal_row(cpr, False)
    wal_lines.append(f"| {cpr * 100:.0f}% | {w1:.2f} | {d1} | {w2:.2f} | {d2} |")
amort = pool - np.cumsum(pool_principal(0.0))
amort_lines = ["| Payment date | Scheduled pool balance (no prepayments, no defaults) | Pool factor |", "|---|---:|---:|"]
for m in range(0, 48, 3):
    y, mth = 2026 + (m + 1) // 12, (m + 1) % 12 + 1
    amort_lines.append(f"| {date(y, mth, 20):%d %B %Y} | {money(max(amort[m], 0))} | {max(amort[m], 0) / pool:.4f} |")

wal_md = f"""# 17. Weighted average lives of the notes

The weighted average life of a note is the average time, in years, from the closing date until each pound of
its principal is repaid, weighted by the principal repaid. It depends on the rate at which borrowers repay
their loans early, which cannot be predicted. The tables below are calculated on the following assumptions
(the "Modelling Assumptions"):

(a) the loans pay their scheduled instalments, and each PCP loan pays its balloon payment on its last
instalment date;

(b) the loans prepay at the constant annual rate shown (the "Constant Prepayment Rate"), applied monthly;

(c) no loan defaults, is in arrears or is repurchased, and no trigger event occurs, so that principal is paid
pro rata to all classes as described in section 4;

(d) the first payment date is [[first_payment_date]] and payments are made on the [[payment_day]] day of each
month;

(e) where stated, the issuer exercises the clean-up call described in Condition 6 on the first payment date on
which the pool balance is less than 10% of the pool balance at the cut-off date.

Because principal is paid pro rata until a trigger event occurs, every class of notes has the same weighted
average life under the Modelling Assumptions. The actual weighted average lives will differ, and the
differences may be material.

**Table 17.1 — Weighted average lives of the Class A, B, C and D Notes**

{chr(10).join(wal_lines)}

**Table 17.2 — Scheduled amortisation of the pool**

{chr(10).join(amort_lines)}
"""

# Renumber the key sections: 1 -> 1, 2 -> 4, 3 -> 10, 4 -> 11, 5 -> 15, 6 -> 16 (headings, tables, references).
NEW = {1: 1, 2: 4, 3: 10, 4: 11, 5: 15, 6: 16}
front, parts = L.split_sections(md, r"^# ")
key = {}
for head, body in parts:
    if head is None:
        continue
    m = re.match(r"^# (\d)\. (.+)$", head)
    if not m:
        continue                                          # the short "Important notice" is replaced
    n = int(m.group(1))
    body = re.sub(r"\bsection (\d)\b", lambda x: f"section {NEW[int(x.group(1))]}", body)
    body = re.sub(r"Table 3\.(\d)", r"Table 10.\1", body)
    key[n] = f"# {NEW[n]}. {m.group(2)}\n" + L.strip_newpages(body)
key[3] = key[3].rstrip() + "\n\n" + "\n".join(extra_tables)

front = front.replace('subtitle: "Prospectus (short form) — £', 'subtitle: "Prospectus — £')
front = front.replace("header-includes:", "toc-title: Contents\nheader-includes:")
cover = f"""
| Class | Initial principal amount | Issue price | Interest rate | Expected rating | Final maturity date |
|---|---:|---:|---|---|---|
""" + "\n".join(f"| Class {c['name']} Notes | {money(terms['initial_note_balances'][c['name']])} | 100% | "
               f"Compounded Daily SONIA + {c['margin'] * 100:.2f}% p.a. | {c['rating']} | "
               f"{date.fromisoformat(FINAL_MATURITY):%d %B %Y} |"
               for c in terms["classes"]) + f"""

Interest is payable monthly at Compounded Daily SONIA plus the margin of each class (section 4). The
notes are asset-backed floating rate notes issued by the issuer and secured on a portfolio of UK motor vehicle
loans originated by [[originator]]. They are offered only to professional investors and are not
listed on any stock exchange.

**Arranger and Lead Manager: Corvane Securities plc**

The date of this prospectus is 26 January 2026.

\\newpage
"""
order = [
    cover, L.section_file("thames", "s00-important-notices.md"), "\\tableofcontents\n",
    key[1], L.section_file("thames", "s02-risk-factors.md"), L.section_file("thames", "s03-transaction-parties.md"),
    key[2], L.section_file("thames", "s05-terms-and-conditions.md"), L.section_file("thames", "s06-use-of-proceeds.md"),
    L.section_file("thames", "s07-issuer-holdings.md"), L.section_file("thames", "s08-originator-servicer.md"),
    L.section_file("thames", "s09-origination-underwriting.md"), key[3], key[4],
    L.section_file("thames", "s12-loan-warranties.md"), L.section_file("thames", "s13-servicing-collections-arrears.md"),
    L.section_file("thames", "s14-cash-management-accounts.md"), key[5], key[6], wal_md,
    L.section_file("thames", "s18-regulatory-disclosures.md"), L.section_file("thames", "s19-taxation.md"),
    L.section_file("thames", "s20-subscription-and-sale.md"), L.section_file("thames", "s21-general-information.md"),
]
body = "\n\n\\newpage\n\n".join(L.fill(x, VALUES).strip() for x in order if x.strip())
OUT.mkdir(parents=True, exist_ok=True)
n_terms = L.build_with_index(front + "\n" + body, "Index of defined terms", OUT, "# Index of defined terms")
print("Wrote", OUT / "prospectus.pdf", f"({n_terms} defined terms in the index)")
