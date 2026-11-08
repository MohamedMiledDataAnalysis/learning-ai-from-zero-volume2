"""Reference solution, chapter 2 practical task: the North West's share of all 90+ arrears."""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[3] / "data" / "servicer_reports"


def nw_share_of_90plus(period):
    s = pd.read_csv(DATA / f"servicer_report_2026_{period:02d}.csv")
    total = s.balance_3_in_arrears.sum()
    nw = s.loc[s.region == "North West", "balance_3_in_arrears"].sum()
    return round(nw / total, 4) if total else 0.0
