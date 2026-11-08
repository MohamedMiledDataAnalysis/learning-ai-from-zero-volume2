"""Final exam, section D: a reference answer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # lets Python find tar_agent
from tar_agent.data import check_period, deal_terms, investor_report  # noqa: E402


def pool_factor_and_cpr(period):
    check_period(period)                                  # raises ValueError for 0, 13, 2.5, "10"...
    pool = investor_report(period)["pool"]
    smm = pool["prepayments"] / (pool["opening_balance"] - pool["principal_received"])
    return {
        "period": period,
        "pool_factor": round(pool["closing_balance"] / deal_terms()["initial_pool_balance"], 6),
        "smm": round(smm, 6),
        "cpr": round(1 - (1 - smm) ** 12, 6),
    }


SCHEMA = {
    "type": "function",
    "function": {
        "name": "pool_factor_and_cpr",
        "description": "Pool factor (closing pool balance / initial pool balance) and prepayment speed "
                       "(SMM and its annual equivalent CPR) for one collection period.",
        "parameters": {
            "type": "object",
            "properties": {"period": {"type": "integer", "minimum": 1, "maximum": 12,
                                      "description": "Collection period: 1 = January 2026, 12 = December 2026."}},
            "required": ["period"],
        },
    },
}
