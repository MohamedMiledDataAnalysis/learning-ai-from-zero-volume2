"""Chapter 2: what is in the deal pack, file by file, as each party sends it.

Run from the repository root:
    python python/vol2/ch02/inventory.py
"""
import json
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"


def show(name, what):
    print(f"{name:<52}{what:>36}")


print(f"{'File (folder/name)':<52}{'What it holds':>36}")
tape = pd.read_csv(DATA / "originator" / "THAMES_2026-1_AUTL_Pool_Cut_2025-12-31.csv", dtype=str)
show("originator/THAMES_2026-1_AUTL_Pool_Cut_2025-12-31.csv", f"{len(tape):,} rows x {tape.shape[1]} fields")
extra = pd.read_csv(DATA / "originator" / "Kestrel_Thames_2026-1_Supplementary_Data_2025-12-31.csv")
show("originator/..._Supplementary_Data_2025-12-31.csv", f"{len(extra):,} rows x {extra.shape[1]} fields")
dictionary = pd.read_excel(DATA / "originator" / "Kestrel_Thames_2026-1_Data_Dictionary.xlsx", sheet_name=None)
show("originator/..._Data_Dictionary.xlsx", f"{len(dictionary)} sheets")
servicer = sorted((DATA / "servicer_reports").glob("*_Servicer_Report_*.xlsx"))
sheets = pd.read_excel(servicer[0], sheet_name=None)
show("servicer_reports/..._Servicer_Report_2026-MM.xlsx", f"{len(servicer)} reports x {len(sheets)} sheets")
level = sorted((DATA / "servicer_reports").glob("*_Loan_Level_Data_*.csv"))
rows = sum(len(pd.read_csv(f)) for f in level)
show("servicer_reports/..._Loan_Level_Data_2026-MM.csv", f"{len(level)} files, {rows:,} rows")
reports = sorted((DATA / "investor_reports").glob("*.pdf"))
show("investor_reports/..._Investor_Report_YYYY-MM-DD.pdf",
     f"{len(reports)} reports x {len(PdfReader(reports[0]).pages)} pages")
excel = sorted((DATA / "investor_reports").glob("*.xlsx"))
show("investor_reports/..._Investor_Report_YYYY-MM-DD.xlsx",
     f"{len(excel)} reports x {len(pd.read_excel(excel[0], sheet_name=None))} sheets")
fca = sorted((DATA / "loan_level").glob("*_AUTL_*.csv"))
fields = pd.read_csv(fca[0], nrows=1).shape[1]
show("loan_level/THAMES_2026-1_AUTL_2026-MM-DD.csv", f"{len(fca)} files x {fields} fields")
ivs = sorted((DATA / "loan_level").glob("*_IVS_*.xlsx"))
show("loan_level/THAMES_2026-1_IVS_2026-MM-DD.xlsx", f"{len(ivs)} files x 3 sheets (IVSS, IVSR, IVSF)")
pages = len(PdfReader(DATA / "prospectus" / "prospectus.pdf").pages)
show("prospectus/prospectus.pdf", f"{pages} pages")
terms = json.loads((DATA / "deal_terms.json").read_text())
show("deal_terms.json", f"{len(terms)} sections")
print()
print("Sheets of the servicer report:", ", ".join(sheets))
print("Sheets of the data dictionary:", ", ".join(dictionary))
