"""Read the cash manager's monthly investor report (PDF or Excel) into the figures the tools use.

Larkmead Bank plc publishes each report twice: a PDF for reading and an Excel workbook with
the same figures. A program cannot use a PDF directly: this module takes the text of each
page in layout mode (one table row per line) and finds each figure by its row label. From
the Excel version it reads the same labels in the cells. Both give the same dictionary:

    pool, arrears, available funds, priority of payments, reserve fund, notes,
    principal deficiency, trigger tests, residual amount to the originator.

The R version (r/taragent/tools/investor_report.R) uses the same labels and rules.
"""

import re
from datetime import date
from functools import lru_cache

from pypdf import PdfReader

NUMBER = r"-?[\d,]+(?:\.\d+)?%?"


def report_lines(pdf_path):
    """Every line of the report, with runs of spaces collapsed to one."""
    lines = []
    for page in PdfReader(pdf_path).pages:
        for line in page.extract_text(extraction_mode="layout").splitlines():
            line = re.sub(r"\s+", " ", line.replace("—", "-")).strip()
            if line:
                lines.append(line)
    return lines


def to_number(text):
    """'1,234.56' -> 1234.56; '4.4000%' -> 0.044 (per cent turned into a fraction)."""
    if text.endswith("%"):
        return round(float(text[:-1].replace(",", "")) / 100, 6)
    value = text.replace(",", "")
    return int(value) if re.fullmatch(r"-?\d+", value) else float(value)


def after(lines, label, count=1):
    """The `count` values that follow `label` on its line (the label can share the line with another table)."""
    # The label starts the line, or follows a value of the table printed to its left.
    values_pattern = " ".join([f"({NUMBER})"] * count)
    pattern = re.compile(r"(?:^|\d |% )" + re.escape(label) + " " + values_pattern)
    for line in lines:
        m = pattern.search(line)
        if m:
            values = [to_number(v) for v in m.groups()]
            return values[0] if count == 1 else values
    raise ValueError(f"investor report: no line with {label!r} followed by {count} value(s)")


def word_after(lines, label):
    for line in lines:
        if line.startswith(label + " "):
            return line[len(label) + 1:].split(" ")[0]
    raise ValueError(f"investor report: no line starting with {label!r}")


def iso(dmy):
    d, m, y = dmy.split("/")
    return date(int(y), int(m), int(d)).isoformat()


def money(x):
    return float(round(float(x), 2))


def read_investor_report(path):
    """Return the report as a dictionary (the same keys, in the same order, for every period and both formats).
    The format is recognised from the file itself: an Excel workbook starts with PK, a PDF with %PDF."""
    with open(path, "rb") as f:
        start = f.read(4)
    if start.startswith(b"PK"):
        return _read_cached(str(path), "xlsx")
    if start.startswith(b"%PDF"):
        return _read_cached(str(path), "pdf")
    raise ValueError(f"{path} is neither a PDF nor an Excel workbook")


@lru_cache(maxsize=32)
def _read_cached(path, kind):
    lines = report_lines(path) if kind == "pdf" else workbook_lines(path)
    return report_from_lines(lines)


def workbook_lines(xlsx_path):
    """Every row of every sheet as one line of text, written the way the PDF shows it: amounts with
    thousands separators and two decimals, ratios as percentages, dates as DD/MM/YYYY. The same rules then
    read both formats."""
    import pandas as pd

    formats = {"Margin": 2, "Coupon": 4}
    lines = []
    for name, sheet in pd.read_excel(xlsx_path, sheet_name=None, header=None).items():
        header = None
        for row in sheet.itertuples(index=False):
            cells = [c for c in row if not (isinstance(c, float) and c != c)]       # drop empty cells (NaN)
            if not cells:
                continue
            if all(isinstance(c, str) for c in cells) and len(cells) > 2:
                header = cells                                                     # a table's header row
                continue
            label = str(cells[0])
            out = [label]
            for k, c in enumerate(cells[1:], start=1):
                column = header[k] if header and k < len(header) else ""
                out.append(_cell_text(label, column, c, formats))
            lines.append(" ".join(out))
    return lines


PERCENT_LABELS = ("Compounded Daily SONIA", "CPR", "Cumulative Default Ratio", "90+ Day Arrears Ratio")


def _cell_text(label, column, value, formats):
    if isinstance(value, str):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            y, m, d = value.split("-")
            return f"{d}/{m}/{y}"
        return value
    if isinstance(value, bool):
        return str(value)
    if column in formats:
        return f"{value * 100:.{formats[column]}f}%"
    if label.startswith(PERCENT_LABELS):
        return f"{value * 100:.4f}%"
    if label in ("Pool Factor",) or column == "Note Factor":
        return f"{value:.6f}"
    if float(value).is_integer() and label in ("Collection Period Number", "Days in Interest Period",
                                               "Number of Loans Outstanding") or column == "Number of Loans":
        return f"{int(value):,}"
    return f"{value:,.2f}"


def report_from_lines(lines):
    """Read the figures from the report's lines (from the PDF or from the Excel workbook)."""
    deal = next(ln for ln in lines if re.fullmatch(r".+ (plc|PLC)", ln))
    pool = {"loans_outstanding": after(lines, "Number of Loans Outstanding")}
    for key, label in [("opening_balance", "Opening Pool Balance"), ("principal_received", "Scheduled Principal Received"),
                       ("prepayments", "Prepayments"), ("defaults", "Defaults"),
                       ("closing_balance", "Closing Pool Balance"), ("interest_collections", "Interest Collections"),
                       ("recoveries", "Recoveries"), ("cumulative_defaults", "Cumulative Defaults"),
                       ("cumulative_recoveries", "Cumulative Recoveries")]:
        pool[key] = money(after(lines, label))
    pool["pool_factor"] = float(after(lines, "Pool Factor"))
    pool["cpr"] = after(lines, "CPR (annualised, this period)")

    arrears = {}
    for k, label in enumerate(["Current (0 instalments)", "1 instalment (30-59 days)", "2 instalments (60-89 days)",
                               "3 instalments (90+ days)"]):
        count, balance = after(lines, "Arrears " + label, 2)
        arrears[f"{k}_instalments"] = {"count": int(count), "balance": money(balance)}

    waterfall = []
    for line in lines:
        m = re.fullmatch(rf"(\d+\. .+?) ({NUMBER}) ({NUMBER})", line)
        if m:
            waterfall.append({"item": m.group(1), "due": money(to_number(m.group(2))),
                              "paid": money(to_number(m.group(3)))})

    notes = []
    for line in lines:
        m = re.fullmatch(rf"Class ([A-Z]) (\S+) (\S+) " + " ".join([f"({NUMBER})"] * 8), line)
        if m:
            v = [to_number(x) for x in m.groups()[3:]]
            notes.append({"class": m.group(1), "rating": m.group(3), "margin": round(v[0], 4), "coupon": v[1],
                          "opening_balance": money(v[3]), "interest_paid": money(v[4]),
                          "principal_paid": money(v[5]), "closing_balance": money(v[6]),
                          "initial_balance": money(v[2]), "factor": float(v[7])})

    def test(label):
        value, limit = after(lines, label, 2)
        result = next(ln for ln in lines if ln.startswith(label + " ")).split(" ")[-1]
        return {"value": value, "limit": limit, "breached": result == "Breached"}

    reserve_result = next(ln for ln in lines if ln.startswith("Reserve Fund at the Required Amount ")).split(" ")[-1]
    return {
        "deal": deal,
        "period": int(after(lines, "Collection Period Number")),
        "collection_period_end": iso(word_after(lines, "Collection Period End Date")),
        "payment_date": iso(word_after(lines, "Payment Date")),
        "sonia": after(lines, "Compounded Daily SONIA for the Interest Period"),
        "pool": pool,
        "arrears": arrears,
        "available_funds": money(after(lines, "Total Available Funds")),
        "waterfall": waterfall,
        "reserve_fund": {"required": money(after(lines, "Reserve Fund Required Amount")),
                         "drawn": money(after(lines, "Reserve Fund Drawn in the Period")),
                         "balance": money(after(lines, "Reserve Fund Balance after the Payment Date"))},
        "notes": notes,
        "principal_deficiency": money(after(lines, "Principal Deficiency after the Payment Date")),
        "triggers": {"cumulative_default_ratio": test("Cumulative Default Ratio"),
                     "arrears_90_ratio": test("90+ Day Arrears Ratio"),
                     "reserve_fund_shortfall": {"breached": reserve_result == "Breached"},
                     "sequential_payment": word_after(lines, "Principal Payment Basis on this Payment Date") == "Sequential",
                     "newly_breached_this_period":
                         word_after(lines, "Trigger Event Occurred in this Collection Period") == "Yes"},
        "residual_to_originator": money(after(lines, "Residual Amount to the Originator")),
    }
