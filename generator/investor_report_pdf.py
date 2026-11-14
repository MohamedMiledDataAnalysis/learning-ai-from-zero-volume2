"""Larkmead Bank plc's monthly investor report for Thames Auto Receivables 2026-1 plc, as a PDF.

The layout follows the investor reports UK cash managers publish: a cover with the
reporting dates and counterparties, then the notes, the collateral, the priority of
payments, the reserve fund and the trigger tests, the performance history, pool tables
and definitions. Every figure has enough decimals for the reader in the agent
(tar_agent/tools/investor_report.py) to recover the exact value.
"""

from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from real_files import (CASH_MANAGER, CONTACT, ISINS, ISSUER, ISSUER_LEI, ORIGINATOR, ORIGINATOR_LEI,
                        TRUSTEE)
from deal_terms import DEAL

DEAL_CLOSING = DEAL["closing_date"]

NAVY = colors.HexColor("#1F2A44")
GOLD = colors.HexColor("#B08D57")
PALE = colors.HexColor("#EEF1F6")

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=8.5, leading=11, alignment=TA_LEFT)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.5, leading=9.5)
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=17, leading=21, textColor=NAVY)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=NAVY, spaceBefore=6,
                    spaceAfter=4)


def m(x):
    return f"{x:,.2f}"


def pct(x, dp=4):
    return f"{x * 100:.{dp}f}%"


def dmy(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def table(rows, widths, header=True, align_right_from=1):
    t = Table(rows, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("FONT", (0, 0), (-1, -1), "Helvetica", 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"),
             ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8CCD4")),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 7.5)]
    for i in range(1 if header else 0, len(rows), 2):
        style.append(("BACKGROUND", (0, i), (-1, i), PALE))
    t.setStyle(TableStyle(style))
    return t


def _page(canvas, doc, rep):
    w, h = landscape(A4)
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 16 * mm, w, 16 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawString(12 * mm, h - 10 * mm, f"{ISSUER} — Monthly Investor Report")
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(w - 12 * mm, h - 10 * mm, f"Payment Date {dmy(rep['payment_date'])}")
    canvas.setFillColor(GOLD)
    canvas.rect(0, h - 17 * mm, w, 1 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#555555"))
    canvas.setFont("Helvetica", 7)
    canvas.drawString(12 * mm, 8 * mm, f"Prepared by {CASH_MANAGER} as Cash Manager. Fictional deal for the book "
                                       "Learning AI from Zero, Volume 2.")
    canvas.drawRightString(w - 12 * mm, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def write_investor_report_pdf(rep, reports, perf, loans, path):
    t = rep["period"]
    end = date.fromisoformat(rep["collection_period_end"])
    start = end.replace(day=1)
    prev_pd = date.fromisoformat(reports[t - 2]["payment_date"]) if t > 1 else date.fromisoformat(DEAL_CLOSING)
    pay = date.fromisoformat(rep["payment_date"])
    p, a, rf, tr = rep["pool"], rep["arrears"], rep["reserve_fund"], rep["triggers"]
    story = []

    # ---- cover
    story += [Spacer(1, 6 * mm), Paragraph(ISSUER, H1),
              Paragraph("Monthly Investor Report", ParagraphStyle("s", parent=H1, fontSize=13, textColor=GOLD)),
              Spacer(1, 5 * mm)]
    dates = [["Reporting dates", ""],
             ["Collection Period Number", str(t)],
             ["Collection Period Start Date", start.strftime("%d/%m/%Y")],
             ["Collection Period End Date", end.strftime("%d/%m/%Y")],
             ["Interest Period Start Date", prev_pd.strftime("%d/%m/%Y")],
             ["Interest Period End Date", pay.strftime("%d/%m/%Y")],
             ["Days in Interest Period", str((pay - prev_pd).days)],
             ["Payment Date", pay.strftime("%d/%m/%Y")]]
    parties = [["Role", "Counterparty"], ["Issuer", ISSUER], ["Issuer LEI", ISSUER_LEI],
               ["Originator, Seller and Servicer", ORIGINATOR], ["Originator LEI", ORIGINATOR_LEI],
               ["Cash Manager, Account Bank, Agent Bank and Principal Paying Agent", CASH_MANAGER],
               ["Trustee", TRUSTEE], ["Corporate Services Provider", "Pellam Corporate Services Ltd"]]
    story.append(Table([[table(dates, [62, 38]), table(parties, [92, 70], align_right_from=9)]],
                       colWidths=[108 * mm, 170 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [Spacer(1, 6 * mm), Paragraph(
        f"Contact: Structured Finance Services, {CASH_MANAGER}, {CONTACT}. This report is prepared by the Cash "
        "Manager from information provided by the Servicer. The Cash Manager has not verified the information "
        "provided by the Servicer and makes no representation as to its accuracy. Capitalised terms have the "
        "meanings given in the Prospectus dated 26 January 2026 and in the definitions at the end of this report.",
        SMALL), PageBreak()]

    # ---- notes
    story.append(Paragraph("1. Notes", H2))
    rows = [["Class", "ISIN", "Rating at Issue", "Margin", "Coupon", "Initial Balance", "Opening Balance",
             "Interest Paid", "Principal Paid", "Closing Balance", "Note Factor"]]
    for n in rep["notes"]:
        rows.append([f"Class {n['class']}", ISINS[n["class"]], n["rating"], pct(n["margin"], 2), pct(n["coupon"]),
                     m(n["initial_balance"]), m(n["opening_balance"]), m(n["interest_paid"]),
                     m(n["principal_paid"]), m(n["closing_balance"]), f"{n['factor']:.6f}"])
    story.append(table(rows, [16, 25, 18, 15, 18, 28, 28, 23, 25, 28, 20], align_right_from=3))
    story += [Spacer(1, 3 * mm),
              table([["Interest rate information", ""],
                     ["Compounded Daily SONIA for the Interest Period", pct(rep["sonia"])],
                     ["Principal Deficiency after the Payment Date", m(rep["principal_deficiency"])]], [90, 40]),
              Spacer(1, 3 * mm)]

    # ---- collateral
    story.append(Paragraph("2. Collateral", H2))
    pool = [["Pool movements in the Collection Period", "Amount (GBP)"],
            ["Opening Pool Balance", m(p["opening_balance"])],
            ["Scheduled Principal Received", m(p["principal_received"])],
            ["Prepayments", m(p["prepayments"])], ["Defaults", m(p["defaults"])],
            ["Closing Pool Balance", m(p["closing_balance"])],
            ["Interest Collections", m(p["interest_collections"])], ["Recoveries", m(p["recoveries"])],
            ["Cumulative Defaults", m(p["cumulative_defaults"])],
            ["Cumulative Recoveries", m(p["cumulative_recoveries"])]]
    stats = [["Pool statistics", "Value"], ["Number of Loans Outstanding", f"{p['loans_outstanding']:,}"],
             ["Pool Factor", f"{p['pool_factor']:.6f}"], ["CPR (annualised, this period)", pct(p["cpr"])]]
    arr = [["Arrears at the end of the Collection Period", "Number of Loans", "Balance (GBP)"]]
    for k, label in enumerate(["Current (0 instalments)", "1 instalment (30-59 days)", "2 instalments (60-89 days)",
                               "3 instalments (90+ days)"]):
        b = a[f"{k}_instalments"]
        arr.append([f"Arrears {label}", f"{b['count']:,}", m(b["balance"])])
    story.append(Table([[table(pool, [72, 34]), [table(stats, [62, 28]), Spacer(1, 3 * mm),
                                                  table(arr, [72, 24, 30])]]],
                       colWidths=[115 * mm, 160 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(PageBreak())

    # ---- priority of payments
    story.append(Paragraph("3. Available Funds and Pre-Enforcement Priority of Payments", H2))
    funds = [["Available Funds", "Amount (GBP)"], ["Interest Collections", m(p["interest_collections"])],
             ["Recoveries", m(p["recoveries"])],
             ["Principal Collections (scheduled principal and prepayments)",
              m(p["principal_received"] + p["prepayments"])],
             ["Reserve Fund Drawing", m(rf["drawn"])], ["Total Available Funds", m(rep["available_funds"])]]
    pop = [["Priority of payments item", "Amount Due", "Amount Paid"]]
    for w in rep["waterfall"]:
        pop.append([w["item"], m(w["due"]), m(w["paid"])])
    pop.append(["Residual Amount to the Originator", "", m(rep["residual_to_originator"])])
    story += [table(funds, [110, 40]), Spacer(1, 4 * mm), table(pop, [110, 40, 40]), PageBreak()]

    # ---- reserve fund and triggers
    story.append(Paragraph("4. Reserve Fund and Trigger Tests", H2))
    res = [["Reserve Fund", "Amount (GBP)"], ["Reserve Fund Required Amount", m(rf["required"])],
           ["Reserve Fund Drawn in the Period", m(rf["drawn"])],
           ["Reserve Fund Balance after the Payment Date", m(rf["balance"])]]
    c, r9 = tr["cumulative_default_ratio"], tr["arrears_90_ratio"]
    trig = [["Test", "Value", "Limit", "Result"],
            ["Cumulative Default Ratio", pct(c["value"]), pct(c["limit"]), "Breached" if c["breached"] else "Pass"],
            ["90+ Day Arrears Ratio", pct(r9["value"]), pct(r9["limit"]), "Breached" if r9["breached"] else "Pass"],
            ["Reserve Fund at the Required Amount", "-", "-",
             "Breached" if tr["reserve_fund_shortfall"]["breached"] else "Pass"]]
    basis = "Sequential" if tr["sequential_payment"] else "Pro rata"
    other = [["Principal payment", "Status"], ["Principal Payment Basis on this Payment Date", basis],
             ["Trigger Event Occurred in this Collection Period", "Yes" if tr["newly_breached_this_period"] else "No"]]
    story += [table(res, [90, 40]), Spacer(1, 4 * mm), table(trig, [90, 30, 30, 30]), Spacer(1, 4 * mm),
              table(other, [90, 40]), Spacer(1, 3 * mm),
              Paragraph("A Trigger Event occurs when the Cumulative Default Ratio exceeds its limit for the period, "
                        "when the 90+ Day Arrears Ratio exceeds its limit, or when the Reserve Fund is below the "
                        "Reserve Fund Required Amount after the Payment Date. Once a Trigger Event has occurred, "
                        "principal is paid sequentially on every later Payment Date.", SMALL), PageBreak()]

    # ---- history
    story.append(Paragraph("5. Performance History", H2))
    hist = [["Period", "Payment Date", "Closing Pool Balance", "Pool Factor", "CPR", "Cumulative Default Ratio",
             "90+ Day Arrears Ratio", "Principal Payment Basis"]]
    for r in reports[:t]:
        hist.append([str(r["period"]), dmy(r["payment_date"]), m(r["pool"]["closing_balance"]),
                     f"{r['pool']['pool_factor']:.6f}", pct(r["pool"]["cpr"], 2),
                     pct(r["triggers"]["cumulative_default_ratio"]["value"], 2),
                     pct(r["triggers"]["arrears_90_ratio"]["value"], 2),
                     "Sequential" if r["triggers"]["sequential_payment"] else "Pro rata"])
    story += [table(hist, [16, 26, 38, 24, 20, 38, 34, 38], align_right_from=1), Spacer(1, 4 * mm)]

    # ---- pool tables at the end of the period
    live = perf[(perf.period == t) & perf.status.isin(["Current", "Arrears"])].merge(
        loans[["loan_id", "product", "region", "fuel_type"]], on="loan_id")
    total = live.closing_balance.sum()

    def strat(col, title, order=None):
        g = live.groupby(col).agg(n=("loan_id", "size"), bal=("closing_balance", "sum"))
        keys = order or sorted(g.index)
        rows = [[title, "Loans", "Balance (GBP)", "% of Balance"]]
        for k in keys:
            if k in g.index:
                rows.append([k, f"{int(g.loc[k, 'n']):,}", m(g.loc[k, "bal"]), f"{g.loc[k, 'bal'] / total:.2%}"])
        rows.append(["Total", f"{len(live):,}", m(total), "100.00%"])
        return table(rows, [44, 18, 32, 22])

    story.append(KeepTogether([Paragraph("6. Pool Stratification at the End of the Collection Period", H2),
                               Table([[strat("product", "Product"), strat("fuel_type", "Fuel type")]],
                                     colWidths=[130 * mm, 130 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")])]))
    story += [Spacer(1, 3 * mm), strat("region", "Region"), PageBreak()]

    # ---- definitions
    story.append(Paragraph("7. Definitions", H2))
    defs = [
        ("Collection Period", "Each calendar month. The first Collection Period is January 2026."),
        ("CPR", "Conditional prepayment rate: the annualised rate of prepayment in the Collection Period, "
                "1 - (1 - SMM)^12, where SMM is prepayments divided by the Opening Pool Balance less scheduled "
                "principal."),
        ("Cumulative Default Ratio", "Cumulative Defaults divided by the Pool Balance at the Cut-off Date."),
        ("90+ Day Arrears Ratio", "Balance of the Loans with 3 instalments in arrears divided by the Closing Pool "
                                  "Balance."),
        ("Defaulted Loan", "A Loan with 4 or more instalments in arrears, or written off by the Servicer."),
        ("Note Factor", "Closing Balance of a Class divided by its Initial Balance."),
        ("Pool Factor", "Closing Pool Balance divided by the Pool Balance at the Cut-off Date."),
        ("Principal Deficiency", "The amount by which the Notes exceed the Closing Pool Balance after the Payment "
                                 "Date."),
        ("Reserve Fund Required Amount", "The amount set out in section 16 of the Prospectus."),
    ]
    story.append(table([["Term", "Definition"]] + [[k, Paragraph(v, SMALL)] for k, v in defs], [55, 200],
                       align_right_from=9))
    story += [Spacer(1, 5 * mm), Paragraph(
        "Disclaimer. This report is provided for information only. It is not an offer to sell or a solicitation of "
        "an offer to buy the Notes. Past performance of the Loans is not an indication of future performance. "
        "Thames Auto Receivables 2026-1 plc and all the parties named in this report are fictional.", SMALL)]

    doc = SimpleDocTemplate(str(path), pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=22 * mm, bottomMargin=14 * mm, title=f"{ISSUER} Investor Report",
                            author=CASH_MANAGER, creator=CASH_MANAGER, invariant=1)
    doc.build(story, onFirstPage=lambda c, d: _page(c, d, rep), onLaterPages=lambda c, d: _page(c, d, rep))
