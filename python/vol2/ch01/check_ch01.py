"""Check the chapter 1 practical task: python python/vol2/ch01/check_ch01.py

Your file my_ch01.py must define excess_spread(period). It is compared with the reference solution.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from common_check import load, report  # noqa: E402
from solution_ch01 import excess_spread as reference  # noqa: E402

m = load(HERE, "ch01")
report([(f"excess_spread({p}) = £{reference(p):,.2f}", abs(m.excess_spread(p) - reference(p)) < 0.01)
        for p in (1, 6, 12)])
