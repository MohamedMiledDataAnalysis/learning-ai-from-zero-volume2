"""Where the deal pack lives, and small helpers to read it.

Every tool reads files through this module, so the folder is set in one place.
Set the environment variable TAR_DATA_DIR to use another copy of the data.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.environ.get("TAR_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

N_PERIODS = 12

STANDARD_REGIONS = [
    "London", "South East", "South West", "East of England", "East Midlands", "West Midlands",
    "North West", "North East", "Yorkshire and the Humber", "Wales", "Scotland", "Northern Ireland",
]


@lru_cache(maxsize=1)
def deal_terms():
    """The deal terms: notes, fees, reserve fund, trigger limits, definitions."""
    return json.loads((DATA_DIR / "deal_terms.json").read_text(encoding="utf-8"))


def period_stem(period):
    """Period 1 -> '2026_01' (the part of the file names that identifies the month)."""
    check_period(period)
    return f"2026_{period:02d}"


def check_period(period):
    if isinstance(period, bool) or not isinstance(period, int) or not 1 <= period <= N_PERIODS:
        raise ValueError(f"period must be a whole number from 1 to {N_PERIODS}, not {period!r}")


def investor_report(period):
    path = DATA_DIR / "investor_reports" / f"investor_report_{period_stem(period)}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def servicer_report(period):
    return pd.read_csv(DATA_DIR / "servicer_reports" / f"servicer_report_{period_stem(period)}.csv")


@lru_cache(maxsize=1)
def loan_performance():
    return pd.read_csv(DATA_DIR / "loan_performance.csv")
