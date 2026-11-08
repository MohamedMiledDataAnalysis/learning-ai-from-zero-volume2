"""Export the monthly surveillance pack to Excel.

    python -m tar_agent.export --period 10 --out ../out

One workbook per period, four sheets: Summary, Triggers, Arrears by region, Note.
"""

import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .data import investor_report
from .tools.note import draft_surveillance_note
from .tools.stratify import stratify_pool
from .tools.triggers import run_trigger_tests

HEADER = Font(bold=True, color="FFFFFF")
FILL = PatternFill("solid", fgColor="1F2F54")


def _sheet(wb, title, header, rows, widths):
    ws = wb.create_sheet(title)
    ws.append(header)
    for cell in ws[1]:
        cell.font, cell.fill = HEADER, FILL
    for row in rows:
        ws.append(row)
    for i, w in enumerate(widths):
        ws.column_dimensions["ABCDEFG"[i]].width = w
    return ws


def export_monthly_pack(period, out_dir):
    """Write out_dir/surveillance_pack_2026_MM.xlsx and return its path."""
    rep = investor_report(period)
    trig = run_trigger_tests(period)
    regions = stratify_pool("region", period, "balance_90plus")["rows"]
    note = draft_surveillance_note(period)["note_markdown"]

    wb = Workbook()
    wb.remove(wb.active)
    pool = rep["pool"]
    _sheet(wb, "Summary", ["Item", "Value"], [
        ["Deal", rep["deal"]],
        ["Collection period", period],
        ["Payment date", rep["payment_date"]],
        ["Opening pool balance", pool["opening_balance"]],
        ["Closing pool balance", pool["closing_balance"]],
        ["Prepayments", pool["prepayments"]],
        ["Defaults", pool["defaults"]],
        ["Recoveries", pool["recoveries"]],
        ["Loans outstanding", pool["loans_outstanding"]],
        ["Principal payment mode", trig["principal_payment_mode"]],
    ], [28, 40])
    _sheet(wb, "Triggers", ["Test", "Value", "Limit", "Headroom", "Breached", "Agrees with report"],
           [[t["test"], t["value"], t["limit"], t["headroom"], "YES" if t["breached"] else "no",
             "yes" if t["agrees_with_report"] else "NO"] for t in trig["tests"]], [28, 12, 10, 12, 10, 18])
    for row in wb["Triggers"].iter_rows(min_row=2, min_col=2, max_col=4):
        for cell in row:
            cell.number_format = "0.00%"            # ratios shown as percentages
    _sheet(wb, "Arrears by region", ["Region", "90+ balance", "Share of 90+", "90+ within region"],
           [[r["group"], r["balance_90plus"], r["share_of_total"], r["ratio_within_group"]] for r in regions],
           [26, 16, 14, 18])
    for row in wb["Arrears by region"].iter_rows(min_row=2):
        row[1].number_format = "#,##0.00"
        row[2].number_format = row[3].number_format = "0.0%"
    _sheet(wb, "Note", ["Surveillance note"], [[line] for line in note.splitlines()], [110])
    for row in wb["Summary"].iter_rows(min_row=5, max_row=9):
        row[1].number_format = "#,##0.00"           # amounts in pounds with two decimals
    wb["Summary"]["B10"].number_format = "#,##0"    # number of loans
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"surveillance_pack_2026_{period:02d}.xlsx"
    wb.properties.creator = "tar_agent"
    wb.save(path)
    return path


def main(argv=None):
    p = argparse.ArgumentParser(description="Export the monthly surveillance pack to Excel.")
    p.add_argument("--period", type=int, required=True)
    p.add_argument("--out", default="../out")
    a = p.parse_args(argv)
    path = export_monthly_pack(a.period, a.out)
    print(f"Wrote {path.name} with sheets: Summary, Triggers, Arrears by region, Note")
    return 0


if __name__ == "__main__":
    sys.exit(main())
