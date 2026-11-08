"""Final exam, section D: your new tool. Fill in the two TODOs, then grade your work:

    python python/vol2/final_exam/grade.py

pool_factor_and_cpr(period) must return a dictionary with these keys:
    period        the period you were given (1 to 12)
    pool_factor   closing pool balance / initial pool balance, rounded to 6 decimals
    smm           prepayments / (opening balance - principal received), rounded to 6 decimals
    cpr           1 - (1 - smm) ** 12, rounded to 6 decimals
It must raise ValueError for a period that is not a whole number from 1 to 12.

SCHEMA must describe the tool for the model, in the same format as python/tar_agent/registry.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent
from tar_agent.data import check_period, deal_terms, investor_report  # noqa: E402,F401


def pool_factor_and_cpr(period):
    # TODO 1: write the function.
    raise NotImplementedError("write pool_factor_and_cpr")


# TODO 2: write the schema.
SCHEMA = {}
