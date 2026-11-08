"""Chapter 1: the key figures of Thames Auto Receivables 2026-1, computed from the deal pack.

Run from the repository root:
    python python/vol2/ch01/deal_figures.py [section]

Sections: october, parties, notes, pool, waterfall, spread, prepayments, defaults, triggers (default: all).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.data import deal_terms, investor_report  # noqa: E402
from tar_agent.tools.loan_tape import load_clean_tape  # noqa: E402

terms = deal_terms()


def parties():
    d = terms["deal"]
    print(f"Issuer (special purpose vehicle): {d['issuer']}")
    print(f"Originator and seller:            {d['originator']}")
    print(f"Servicer:                         {d['servicer']}")
    print(f"Trustee:                          {d['trustee']}")
    print(f"Cut-off date {d['cut_off_date']}, closing date {d['closing_date']}, "
          f"first payment date {d['first_payment_date']}")


def notes():
    """Each class and the protection below it. A reserve fund counts in the credit enhancement (CE) only if
    it can pay principal or cover losses; the Thames reserve fund pays only fees and interest."""
    total = sum(terms["initial_note_balances"].values())
    reserve = terms["reserve_fund_required_amount"]
    counted = terms["reserve_fund"]["can_cover_losses"]
    support = reserve if counted else 0.0
    print(f"{'Class':<6}{'Balance':>16}{'Share':>8}{'Margin':>9}{'Rating':>8}{'Subord.':>9}{'CE':>8}")
    below = total
    for c in terms["classes"]:
        bal = terms["initial_note_balances"][c["name"]]
        below = round(below - bal, 2)                 # the classes ranked after this one
        print(f"{c['name']:<6}{bal:>16,.2f}{bal / total:>8.2%}{c['margin']:>9.2%}{c['rating']:>8}"
              f"{below / total:>9.2%}{(below + support) / total:>8.2%}")
    print(f"Total notes {total:,.2f}; reserve fund {reserve:,.2f} ({reserve / total:.2%} of the notes), "
          f"{'counted in CE' if counted else 'not counted in CE: it pays only fees and interest'}")


def pool():
    tape = load_clean_tape()
    bal = tape.current_balance
    print(f"Loans: {len(tape):,}   Pool balance: £{bal.sum():,.2f}   Average loan: £{bal.mean():,.2f}")
    print(f"Weighted average interest rate: {(tape.interest_rate_pct * bal).sum() / bal.sum():.2f}%")
    pcp = tape[tape["product"] == "PCP"]
    print(f"PCP loans: {len(pcp):,} ({pcp.current_balance.sum() / bal.sum():.2%} of the balance); "
          f"balloon payments due: £{pcp.balloon_amount.sum():,.2f}")


def waterfall(period=1):
    rep = investor_report(period)
    print(f"Period {period}: available funds £{rep['available_funds']:,.2f}")
    for line in rep["waterfall"]:
        print(f"  {line['item']:<46}{line['paid']:>14,.2f}")


def spread(period=1):
    """Excess spread: the interest that remains after fees and note interest."""
    rep = investor_report(period)
    w = {line["item"]: line["paid"] for line in rep["waterfall"]}
    fees = w["1. Servicer fee"] + w["1. Trustee fee"]
    note_interest = sum(n["interest_paid"] for n in rep["notes"])
    interest = rep["pool"]["interest_collections"]
    excess = interest - fees - note_interest
    pool_open = rep["pool"]["opening_balance"]
    print(f"Interest collected £{interest:,.2f} - fees £{fees:,.2f} - note interest £{note_interest:,.2f}")
    print(f"= excess spread £{excess:,.2f}, that is {excess / pool_open * 12:.2%} a year of the pool balance")


def prepayments():
    """Single monthly mortality (SMM) and its annual version, the conditional prepayment rate (CPR)."""
    print(f"{'Period':>6}{'Prepaid':>14}{'Balance due':>15}{'SMM':>8}{'CPR':>8}")
    for period in (1, 4, 8, 12):
        p = investor_report(period)["pool"]
        due = p["opening_balance"] - p["principal_received"]        # balance that could have been prepaid
        smm = p["prepayments"] / due
        print(f"{period:>6}{p['prepayments']:>14,.2f}{due:>15,.2f}{smm:>8.2%}{1 - (1 - smm) ** 12:>8.2%}")


def defaults():
    print(f"{'Period':>6}{'Defaults':>12}{'Monthly rate':>13}{'Annual rate':>12}{'Cumulative ratio':>17}")
    for period in (4, 8, 10, 12):
        rep = investor_report(period)
        p = rep["pool"]
        mdr = p["defaults"] / p["opening_balance"]
        print(f"{period:>6}{p['defaults']:>12,.2f}{mdr:>13.3%}{1 - (1 - mdr) ** 12:>12.2%}"
              f"{rep['triggers']['cumulative_default_ratio']['value']:>17.2%}")
    p = investor_report(12)["pool"]
    print(f"Cumulative defaults £{p['cumulative_defaults']:,.2f}; recoveries received £{p['cumulative_recoveries']:,.2f}")


def triggers():
    for period in (9, 10):
        t = investor_report(period)["triggers"]
        a, c = t["arrears_90_ratio"], t["cumulative_default_ratio"]
        print(f"Period {period}: 90+ arrears {a['value']:.2%} (limit {a['limit']:.2%}), cumulative defaults "
              f"{c['value']:.2%} (limit {c['limit']:.2%}), principal "
              f"{'sequential' if t['sequential_payment'] else 'pro rata'}")


def october():
    """Period 10: the month of the trigger breach."""
    waterfall(10)
    spread(10)
    for n in investor_report(10)["notes"]:
        print(f"  Class {n['class']}: principal paid {n['principal_paid']:>14,.2f}")


SECTIONS = {"october": october, "parties": parties, "notes": notes, "pool": pool, "waterfall": waterfall, "spread": spread,
            "prepayments": prepayments, "defaults": defaults, "triggers": triggers}

if __name__ == "__main__":
    chosen = sys.argv[1:] or [k for k in SECTIONS if k != "october"]
    for name in chosen:
        if len(chosen) > 1:
            print(f"--- {name}")
        SECTIONS[name]()
