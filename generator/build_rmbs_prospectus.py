"""Build the Severn Residential Mortgages 2026-1 plc prospectus (PDF) from generator/rmbs_terms.py.

Run from the repository root:

    python generator/build_rmbs_prospectus.py

Writes data/prospectus_rmbs/prospectus.md and prospectus.pdf. Needs pandoc and XeLaTeX.
The layout and vocabulary are deliberately different from the Thames prospectus (dates
written in words, "per cent", lettered priorities of payments, a notes table without "£"),
so that the Prospectus Analyser of Volume 2 Part E meets a document its rules were not written for.
"""

import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rmbs_terms as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "prospectus_rmbs"
D = T.DEAL
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def words_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def amount(x):
    return f"{x:,.0f}" if x == int(x) else f"{x:,.2f}"


def per_cent(x, dp=2):
    return f"{x * 100:.{dp}f} per cent"


def split_counts(total, shares):
    """Whole numbers that add up to `total`, proportional to `shares` (largest remainder)."""
    raw = [total * s for s in shares]
    out = [int(r) for r in raw]
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - out[i], reverse=True)[: total - sum(out)]:
        out[i] += 1
    return out


def split_money(total, shares):
    pence = split_counts(int(round(total * 100)), shares)
    return [p / 100 for p in pence]


def reserve_amount(r):
    return round(r["percent"] * sum(c["balance"] for c in T.CLASSES if c["name"] in r["basis"]), 2)


notes_total = sum(c["balance"] for c in T.CLASSES)
assert abs(notes_total - D["pool_balance"]) < 0.005

def margin_text(m):
    """0.0058 -> '0.58%', 0.01425 -> '1.425%' (no trailing zeros beyond two decimals)."""
    if m is None:
        return "n/a"
    text = f"{m * 100:.3f}"
    return (text[:-1] if text.endswith("0") else text) + "%"


note_rows = "\n".join(
    f"| {c['name']} | {amount(c['balance'])} | {c['balance'] / notes_total * 100:.2f} | "
    f"{'Compounded Daily SONIA' if c['margin'] is not None else 'None'} | {margin_text(c['margin'])} | "
    f"{margin_text(c['step_up_margin'])} | {c['rating']} |"
    for c in T.CLASSES)

reserve_rows = "\n".join(
    f"| {r['name']} | {per_cent(r['percent'])} of the Class {', '.join(r['basis'][:-1])}"
    f"{' and ' if len(r['basis']) > 1 else ''}{r['basis'][-1]} Notes | {amount(reserve_amount(r))} |"
    for r in T.RESERVES)


def strat_table(title, rows):
    shares = [s for _, s, _ in rows]
    counts = split_counts(D["n_loans"], [n for _, _, n in rows])
    money = split_money(D["pool_balance"], shares)
    out = [f"**{title}**", "", "| Band | Number of loans | Current balance (£) | % of balance |", "|---|---:|---:|---:|"]
    for (label, s, _), n, m in zip(rows, counts, money):
        out.append(f"| {label} | {n:,} | {m:,.2f} | {s * 100:.2f} |")
    out.append(f"| **Total** | **{sum(counts):,}** | **{sum(money):,.2f}** | **100.00** |")
    return "\n".join(out) + "\n"


def lettered(items):
    return "\n".join(f"({LETTERS[i]}) {text};" if i < len(items) - 1 else f"({LETTERS[i]}) {text}."
                     for i, text in enumerate(items))


trigger_text = []
for t in T.TRIGGERS:
    if t.get("direction") == "below":
        trigger_text.append(f"- **{t['name']}**: on any Interest Payment Date, the {t['measure']} is less than "
                            f"{per_cent(t['limit'], 0)}.")
    else:
        trigger_text.append(f"- **{t['name']}**: on any Calculation Date, the {t['measure']} exceeds "
                            f"{per_cent(t['limit'])}.")
trigger_text = "\n".join(trigger_text)

S = T.POOL_STATS
md = f"""---
title: "{D['issuer']}"
subtitle: "Residential Mortgage-Backed Floating Rate Notes due {date.fromisoformat(D['final_maturity_date']).year}"
date: "Issue Date: {words_date(D['issue_date'])}"
geometry: "a4paper, margin=2.2cm"
mainfont: "TeX Gyre Pagella"
sansfont: "TeX Gyre Heros"
fontsize: 11pt
header-includes:
  - \\usepackage{{fancyhdr}}
  - \\pagestyle{{fancy}}
  - \\fancyhf{{}}
  - \\fancyhead[L]{{\\small Severn Residential Mortgages 2026-1 plc}}
  - \\fancyhead[R]{{\\small Offering circular}}
  - \\fancyfoot[C]{{\\small - \\thepage\\ -}}
  - \\fancypagestyle{{plain}}{{\\fancyhf{{}}\\fancyfoot[C]{{\\small - \\thepage\\ -}}\\renewcommand{{\\headrulewidth}}{{0pt}}}}
---

## Important notice {{-}}

This offering circular is a teaching document written for the book *Learning AI from Zero — Build Your Own AI
Agent*. The Issuer, the Seller, the trustee, the banks and every mortgage loan described here are fictional.
Any resemblance to a real company or person is a coincidence. It is shorter than a real offering circular,
which runs to several hundred pages, and it is laid out differently from the Thames Auto Receivables
prospectus on purpose: dates are written in words, percentages are written "per cent", and the priorities
of payments are lettered.

Capitalised terms are defined in the Glossary of Defined Terms at the end of this document.

\\newpage

## Key Terms {{-}}

| Term | Detail |
|---|---|
| Issuer | {D['issuer']} |
| Seller | {D['seller']} |
| Mortgage Administrator | {D['mortgage_administrator']} |
| Cash Manager | {D['cash_manager']} |
| Note Trustee and Security Trustee | {D['trustee']} |
| Issuer Account Bank and Swap Provider | {D['account_bank']} |
| Arranger | {D['arranger']} |
| Portfolio Reference Date | {words_date(D['portfolio_reference_date'])} |
| Issue Date | {words_date(D['issue_date'])} |
| First Interest Payment Date | {words_date(D['first_interest_payment_date'])} |
| Interest Payment Dates | The {D['interest_payment_day']}th day of {D['interest_payment_months']} |
| Step-Up Date | {words_date(D['step_up_date'])} |
| Final Maturity Date | {words_date(D['final_maturity_date'])} |
| Denomination | Sterling |
| Provisional Portfolio | {D['n_loans']:,} first-ranking residential mortgage loans |
| Aggregate current balance of the Provisional Portfolio | {amount(D['pool_balance'])} |

**Overview.** On the Issue Date the Issuer will buy the Provisional Portfolio from the Seller and pay for it
with the proceeds of the Notes. The Mortgage Administrator will continue to collect the borrowers' monthly
payments. The Cash Manager will apply the receipts on each Interest Payment Date, quarterly, in the orders set
out in the Revenue Priority of Payments and the Principal Priority of Payments.

\\newpage

## Section 1 — The Notes {{-}}

| Class | Principal amount | % of Notes | Reference rate | Margin to Step-Up Date | Margin after Step-Up Date | Expected rating |
|---|---:|---:|---|---:|---:|---|
{note_rows}

The Notes are denominated in sterling; the principal amounts above are in pounds. Interest on the Class A,
Class B, Class C and Class D Notes is payable quarterly in arrear on each Interest Payment Date at Compounded
Daily SONIA plus the relevant margin. The Class Z Notes do not bear interest.

**Step-up and optional redemption.** From the Step-Up Date the margins increase to those shown in the last
margin column. On the Step-Up Date and on any Interest Payment Date after it, the Issuer may redeem all (but
not some) of the Notes at their principal amount outstanding plus accrued interest. The Issuer may also redeem
all the Notes on any Interest Payment Date on which the current balance of the portfolio is less than 10 per
cent of its balance on the Issue Date.

**Final redemption.** Unless redeemed earlier, the Notes will be redeemed on the Final Maturity Date.

\\newpage

## Section 2 — Credit Structure {{-}}

**Subordination.** Payments on the Notes are made in order of seniority: the Class A Notes rank ahead of the
Class B Notes, which rank ahead of the Class C Notes, and so on down to the Class Z Notes. The Class Z Notes
absorb losses first. On the Issue Date the Notes ranking below the Class A Notes represent
{per_cent(sum(c['balance'] for c in T.CLASSES[1:]) / notes_total)} of all the Notes.

**Reserve funds.** Two reserve funds will be funded on the Issue Date from the proceeds of a Subordinated Loan
made by the Seller:

| Reserve | Required amount | Amount on the Issue Date (£) |
|---|---|---:|
{reserve_rows}

The General Reserve Fund {T.RESERVES[0]['use']}. The Liquidity Reserve Fund {T.RESERVES[1]['use']}.
Each reserve fund is topped up to its required amount from Available Revenue Receipts in the order set out in
Section 3.

**Principal Deficiency Ledger.** Realised losses, and principal receipts used to pay revenue items, are recorded
on the Principal Deficiency Ledger, starting with the Class Z sub-ledger and moving up to the Class A
sub-ledger. Excess revenue clears the sub-ledgers in order of seniority.

**Interest rate swap.** Most loans pay a fixed rate for two or five years while the Notes pay a floating rate.
The Issuer enters into a swap with the Swap Provider to cover this difference.

\\newpage

## Section 3 — Revenue Priority of Payments {{-}}

Before the delivery of an enforcement notice, the Cash Manager will apply the Available Revenue Receipts on
each Interest Payment Date in the following order of priority (in each case only if and to the extent that
the payments of higher priority have been made in full):

{lettered(T.REVENUE_PRIORITY)}

If the Available Revenue Receipts are not enough to pay items (a) to (d) and the interest on the Class B
Notes, the Liquidity Reserve Fund is drawn first and then the General Reserve Fund. The General Reserve Fund
also covers the interest on the Class C and Class D Notes.

\\newpage

## Section 4 — Principal Priority of Payments {{-}}

Before the delivery of an enforcement notice, the Cash Manager will apply the Available Principal Receipts on
each Interest Payment Date in the following order of priority:

{lettered(T.PRINCIPAL_PRIORITY)}

Item (a) means any amount of Available Principal Receipts needed to pay a shortfall of senior expenses or of
interest on the most senior class of Notes outstanding; the amount used is recorded on the Principal
Deficiency Ledger.

**Pro rata payment.** Until a Sequential Payment Trigger occurs, and provided the credit enhancement of the
Class A Notes is at least twice its level on the Issue Date, items (b) to (e) are paid pro rata to the
principal amount outstanding of the Class A, Class B, Class C and Class D Notes. Otherwise they are paid
sequentially in the order shown.

\\newpage

## Section 5 — Trigger Events {{-}}

A **Sequential Payment Trigger** occurs if any of the following events happens:

{trigger_text}

Once a Sequential Payment Trigger has occurred, principal is paid sequentially, the Class A Notes first,
and the switch is permanent.

\\newpage

## Section 6 — The Provisional Portfolio {{-}}

The tables below describe the Provisional Portfolio on the Portfolio Reference Date. Percentages are
percentages of the aggregate current balance of {amount(D['pool_balance'])} pounds.

| Characteristic | Value |
|---|---:|
| Number of loans | {D['n_loans']:,} |
| Average current balance | {D['pool_balance'] / D['n_loans']:,.2f} |
| Weighted average current loan-to-value | {S['weighted_average_current_ltv'] * 100:.1f}% |
| Weighted average indexed loan-to-value | {S['weighted_average_indexed_ltv'] * 100:.1f}% |
| Weighted average interest rate | {S['weighted_average_interest_rate'] * 100:.2f}% |
| Weighted average seasoning | {S['weighted_average_seasoning_months']} months |
| Weighted average remaining term | {S['weighted_average_remaining_term_years']} years |

{strat_table('Table 6.1 — Current loan-to-value', T.STRATS['Current loan-to-value'])}

{strat_table('Table 6.2 — Indexed loan-to-value', T.STRATS['Indexed loan-to-value'])}

\\newpage

{strat_table('Table 6.3 — Region', T.STRATS['Region'])}

{strat_table('Table 6.4 — Interest type', T.STRATS['Interest type'])}

{strat_table('Table 6.5 — Borrower type', T.STRATS['Borrower type'])}

{strat_table('Table 6.6 — Repayment type', T.STRATS['Repayment type'])}

\\newpage

## Section 7 — Lending Criteria and Loan Warranties {{-}}

The Seller originated every loan under its lending criteria, which require an affordability assessment, a
credit search, verification of income and a valuation of the property by an approved valuer.

On the Issue Date the Seller will give the following warranties about each loan:

{lettered([w.rstrip('.') for w in T.LOAN_WARRANTIES])}

If a warranty proves untrue and the breach cannot be remedied, the Seller must buy the loan back at its
current balance plus accrued interest.

\\newpage

## Section 8 — Servicing and Arrears Management {{-}}

The Mortgage Administrator services the loans under the mortgage administration agreement for a fee of
{per_cent(T.FEES['mortgage_administrator_fee'])} per year of the current balance of the portfolio. It applies
the Seller's arrears policy: a borrower who misses a payment is contacted within ten days, offered a payment
arrangement where appropriate, and possession is sought only as a last resort and in line with the rules of
the Financial Conduct Authority on fair treatment of customers in financial difficulty.

The Cash Manager receives {amount(T.FEES['cash_manager_fee'])} pounds per year and the Note Trustee and Security
Trustee receives {amount(T.FEES['trustee_fee'])} pounds per year.

\\newpage

## Section 9 — Risk Retention {{-}}

{T.RISK_RETENTION} The Seller will not sell, hedge or otherwise mitigate the credit risk of the retained
exposures, and will confirm its retention in each quarterly investor report.

## Section 10 — Risk Factors {{-}}

**Credit risk.** Payments on the Notes depend on borrowers paying their loans. Losses not covered by excess
revenue, the reserve funds and subordination will reduce the payments on the Notes.

**Interest rate risk.** Fixed-rate loans reset to the standard variable rate after their initial period; the
swap covers the fixed-rate period only.

**Prepayment risk.** Borrowers may repay early, for example when their fixed-rate period ends, which changes
the timing of principal payments on the Notes.

**House price risk.** A fall in house prices raises loan-to-value ratios and may increase realised losses.

\\newpage

## Glossary of Defined Terms {{-}}

""" + "\n".join(f'"**{term}**" means {text}.\n' for term, text in T.DEFINITIONS.items()) + """
"**Interest Payment Date**" means the 20th day of January, April, July and October in each year.

"**Calculation Date**" means the last day of the month before each Interest Payment Date.
"""

OUT.mkdir(parents=True, exist_ok=True)
(OUT / "prospectus.md").write_text(md, encoding="utf-8")
subprocess.run(["pandoc", str(OUT / "prospectus.md"), "-o", str(OUT / "prospectus.pdf"), "--pdf-engine=xelatex"],
               check=True, env={**os.environ, "SOURCE_DATE_EPOCH": "1767225600", "FORCE_SOURCE_DATE": "1"})
# The PDF's trailer ID is derived from pandoc's temporary folder name; fix it so every build is byte-identical.
pdf = (OUT / "prospectus.pdf").read_bytes()
pdf = re.sub(rb"/ID\[<[0-9a-f]{32}><[0-9a-f]{32}>\]", b"/ID[<" + b"0" * 32 + b"><" + b"0" * 32 + b">]", pdf)
(OUT / "prospectus.pdf").write_bytes(pdf)
print("Wrote", OUT / "prospectus.pdf")
