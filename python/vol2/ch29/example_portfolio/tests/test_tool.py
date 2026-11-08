"""A minimal test for the example portfolio: the pool factor falls over the year."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "final_exam" / "solution"))
from reference import pool_factor_and_cpr  # noqa: E402


def test_pool_factor_falls():
    assert pool_factor_and_cpr(12)["pool_factor"] < pool_factor_and_cpr(1)["pool_factor"] < 1
