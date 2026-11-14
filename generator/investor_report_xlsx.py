"""Larkmead Bank plc's monthly investor report, Excel version.

Cash managers publish the investor report as a PDF for reading and as an Excel workbook
for analysts who load the figures into their own models. The workbook holds the same
figures as the PDF, one sheet per section. Amounts are numbers, ratios are fractions shown
with a percentage format, as in any Excel file: the cell holds 0.138497, the screen shows
13.8497%.
"""

from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Font

from real_files import (CASH_MANAGER, ISINS, ISSUER, ISSUER_LEI, ORIGINATOR, ORIGINATOR_LEI, TRUSTEE, _header,
                        _save)
from deal_terms import DEAL

MONEY, PCT4, PCT2, FACTOR = "#,##0.00", "0.0000%", "0.00%", "0.000000"


def _pairs(ws, start_row, rows, formats=None):
    """Write (label, value) rows in columns A and B."""
    for i, (label, value) in enumerate(rows, start=start_row):
        ws.cell(row=i, column=1, value=label).font = Font(name="Arial", size=9)
        c = ws.cell(row=i, column=2, value=value)
        c.font = Font(name="Arial", size=9)
        if formats and label in formats:
            c.number_format = formats[label]
        elif isinstance(value, float):
            c.number_format = MONEY
    ws.column_dimensions["A"].width = 52
    ws.column_dimensions["B"].width = 22


def write_investor_report_xlsx(rep, reports, path):
    t = rep["period"]
    end = date.fromisoformat(rep["collection_period_end"])
    prev = date.fromisoformat(reports[t - 2]["payment_date"]) if t > 1 else date.fromisoformat(DEAL["closing_date"])
    pay = date.fromisoformat(rep["payment_date"])
    p, a, rf, tr = rep["pool"], rep["arrears"], rep["reserve_fund"], rep["triggers"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Cover"
    ws.cell(row=1, column=1, value=ISSUER).font = Font(name="Arial", size=13, bold=True, color="1F2A44")
    ws.cell(row=2, column=1, value="Monthly Investor Report").font = Font(name="Arial", size=11, color="B08D57")
    _pairs(ws, 4, [("Collection Period Number", t), ("Collection Period Start Date", end.replace(day=1).isoformat()),
                   ("Collection Period End Date", end.isoformat()), ("Interest Period Start Date", prev.isoformat()),
                   ("Interest Period End Date", pay.isoformat()), ("Days in Interest Period", (pay - prev).days),
                   ("Payment Date", pay.isoformat()), ("Issuer", ISSUER), ("Issuer LEI", ISSUER_LEI),
                   ("Originator, Seller and Servicer", ORIGINATOR), ("Originator LEI", ORIGINATOR_LEI),
                   ("Cash Manager", CASH_MANAGER), ("Trustee", TRUSTEE),
                   ("Prepared by", f"{CASH_MANAGER} as Cash Manager, from information provided by the Servicer")])

    ws = wb.create_sheet("Notes")
    cols = ["Class", "ISIN", "Rating at Issue", "Margin", "Coupon", "Initial Balance", "Opening Balance",
            "Interest Paid", "Principal Paid", "Closing Balance", "Note Factor"]
    _header(ws, 1, cols)
    fmts = [None, None, None, PCT2, PCT4, MONEY, MONEY, MONEY, MONEY, MONEY, FACTOR]
    for i, n in enumerate(rep["notes"], start=2):
        values = [f"Class {n['class']}", ISINS[n["class"]], n["rating"], n["margin"], n["coupon"],
                  n["initial_balance"], n["opening_balance"], n["interest_paid"], n["principal_paid"],
                  n["closing_balance"], n["factor"]]
        for j, (v, f) in enumerate(zip(values, fmts), start=1):
            c = ws.cell(row=i, column=j, value=v)
            if f:
                c.number_format = f
    _pairs(ws, len(rep["notes"]) + 3, [("Compounded Daily SONIA for the Interest Period", rep["sonia"]),
                                         ("Principal Deficiency after the Payment Date", rep["principal_deficiency"])],
           {"Compounded Daily SONIA for the Interest Period": PCT4})

    ws = wb.create_sheet("Collateral")
    _pairs(ws, 1, [("Opening Pool Balance", p["opening_balance"]),
                   ("Scheduled Principal Received", p["principal_received"]), ("Prepayments", p["prepayments"]),
                   ("Defaults", p["defaults"]), ("Closing Pool Balance", p["closing_balance"]),
                   ("Interest Collections", p["interest_collections"]), ("Recoveries", p["recoveries"]),
                   ("Cumulative Defaults", p["cumulative_defaults"]),
                   ("Cumulative Recoveries", p["cumulative_recoveries"]),
                   ("Number of Loans Outstanding", p["loans_outstanding"]), ("Pool Factor", p["pool_factor"]),
                   ("CPR (annualised, this period)", p["cpr"])],
           {"Pool Factor": FACTOR, "CPR (annualised, this period)": PCT4, "Number of Loans Outstanding": "#,##0"})
    _header(ws, 15, ["Arrears", "Number of Loans", "Balance (GBP)"])
    for k, label in enumerate(["Current (0 instalments)", "1 instalment (30-59 days)", "2 instalments (60-89 days)",
                               "3 instalments (90+ days)"]):
        b = a[f"{k}_instalments"]
        ws.cell(row=16 + k, column=1, value=f"Arrears {label}")
        ws.cell(row=16 + k, column=2, value=b["count"])
        ws.cell(row=16 + k, column=3, value=b["balance"]).number_format = MONEY

    ws = wb.create_sheet("Priority of Payments")
    _pairs(ws, 1, [("Interest Collections", p["interest_collections"]), ("Recoveries", p["recoveries"]),
                   ("Principal Collections (scheduled principal and prepayments)",
                    round(p["principal_received"] + p["prepayments"], 2)),
                   ("Reserve Fund Drawing", rf["drawn"]), ("Total Available Funds", rep["available_funds"])])
    _header(ws, 7, ["Priority of payments item", "Amount Due", "Amount Paid"])
    for i, w in enumerate(rep["waterfall"], start=8):
        ws.cell(row=i, column=1, value=w["item"])
        ws.cell(row=i, column=2, value=w["due"]).number_format = MONEY
        ws.cell(row=i, column=3, value=w["paid"]).number_format = MONEY
    last = 8 + len(rep["waterfall"])
    ws.cell(row=last, column=1, value="Residual Amount to the Originator")
    ws.cell(row=last, column=3, value=rep["residual_to_originator"]).number_format = MONEY

    ws = wb.create_sheet("Reserve Fund and Triggers")
    _pairs(ws, 1, [("Reserve Fund Required Amount", rf["required"]), ("Reserve Fund Drawn in the Period", rf["drawn"]),
                   ("Reserve Fund Balance after the Payment Date", rf["balance"])])
    _header(ws, 5, ["Test", "Value", "Limit", "Result"])
    c, r9 = tr["cumulative_default_ratio"], tr["arrears_90_ratio"]
    rows = [("Cumulative Default Ratio", c["value"], c["limit"], "Breached" if c["breached"] else "Pass"),
            ("90+ Day Arrears Ratio", r9["value"], r9["limit"], "Breached" if r9["breached"] else "Pass"),
            ("Reserve Fund at the Required Amount", None, None,
             "Breached" if tr["reserve_fund_shortfall"]["breached"] else "Pass")]
    for i, row in enumerate(rows, start=6):
        for j, v in enumerate(row, start=1):
            cell = ws.cell(row=i, column=j, value=v)
            if j in (2, 3) and v is not None:
                cell.number_format = PCT4
    _pairs(ws, 10, [("Principal Payment Basis on this Payment Date",
                     "Sequential" if tr["sequential_payment"] else "Pro rata"),
                    ("Trigger Event Occurred in this Collection Period",
                     "Yes" if tr["newly_breached_this_period"] else "No")])

    ws = wb.create_sheet("Performance History")
    _header(ws, 1, ["Period", "Payment Date", "Closing Pool Balance", "Pool Factor", "CPR", "Cumulative Default Ratio",
                    "90+ Day Arrears Ratio", "Principal Payment Basis"])
    for i, r in enumerate(reports[:t], start=2):
        values = [r["period"], r["payment_date"], r["pool"]["closing_balance"], r["pool"]["pool_factor"],
                  r["pool"]["cpr"], r["triggers"]["cumulative_default_ratio"]["value"],
                  r["triggers"]["arrears_90_ratio"]["value"],
                  "Sequential" if r["triggers"]["sequential_payment"] else "Pro rata"]
        for j, (v, f) in enumerate(zip(values, [None, None, MONEY, FACTOR, PCT2, PCT2, PCT2, None]), start=1):
            cell = ws.cell(row=i, column=j, value=v)
            if f:
                cell.number_format = f
    _save(wb, path)
