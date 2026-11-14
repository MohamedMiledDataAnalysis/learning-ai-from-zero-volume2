"""Reference solution, chapter 2 practical task: the North West's share of all 90+ arrears."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.data import servicer_report  # noqa: E402   the Regional sheet of Kestrel's servicer report


def nw_share_of_90plus(period):
    s = servicer_report(period)
    total = s.balance_3_in_arrears.sum()
    nw = s.loc[s.region == "North West", "balance_3_in_arrears"].sum()
    return round(nw / total, 4) if total else 0.0
