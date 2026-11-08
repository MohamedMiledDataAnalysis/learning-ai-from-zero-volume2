"""Chapter 2: what is in the deal pack, file by file.

Run from the repository root:
    python python/vol2/ch02/inventory.py
"""
import json
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"

print(f"{'File':<44}{'What it holds':>34}")
for name in ["loan_tape_cutoff.csv", "loan_performance.csv", "loan_tape_2026_12.csv"]:
    df = pd.read_csv(DATA / name)
    print(f"{name:<44}{f'{len(df):,} rows x {df.shape[1]} columns':>34}")
reports = sorted((DATA / "investor_reports").glob("*.json"))
print(f"{'investor_reports/*.json and *.md':<44}{f'{len(reports)} monthly reports':>34}")
servicer = sorted((DATA / "servicer_reports").glob("*.csv"))
rows = len(pd.read_csv(servicer[0]))
print(f"{'servicer_reports/*.csv':<44}{f'{len(servicer)} reports x {rows} regions':>34}")
pages = len(PdfReader(DATA / "prospectus" / "prospectus.pdf").pages)
print(f"{'prospectus/prospectus.pdf':<44}{f'{pages} pages':>34}")
terms = json.loads((DATA / "deal_terms.json").read_text())
print(f"{'deal_terms.json':<44}{f'{len(terms)} sections':>34}")
print()
print("Sections of deal_terms.json:", ", ".join(terms))
