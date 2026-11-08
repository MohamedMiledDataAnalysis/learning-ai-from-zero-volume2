"""Reference solution, chapter 1 practical task: excess spread of any period."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.data import investor_report  # noqa: E402


def excess_spread(period):
    rep = investor_report(period)
    paid = {line["item"]: line["paid"] for line in rep["waterfall"]}
    fees = paid["1. Servicer fee"] + paid["1. Trustee fee"]
    note_interest = sum(n["interest_paid"] for n in rep["notes"])
    return round(rep["pool"]["interest_collections"] - fees - note_interest, 2)
