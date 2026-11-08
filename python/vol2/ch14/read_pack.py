"""Chapter 14: export the pack for period 10 and read it back."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

import tempfile

import openpyxl

from tar_agent.export import export_monthly_pack

with tempfile.TemporaryDirectory() as folder:
    path = export_monthly_pack(10, folder)
    wb = openpyxl.load_workbook(path)
    print("File:", path.name)
    for ws in wb.worksheets:
        print(f"Sheet '{ws.title}': {ws.max_row} rows x {ws.max_column} columns")
    print()
    for row in wb["Triggers"].iter_rows(values_only=True):
        print(row)
