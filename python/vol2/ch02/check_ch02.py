"""Check the chapter 2 practical task: python python/vol2/ch02/check_ch02.py

Your file my_ch02.py must define nw_share_of_90plus(period), returning a fraction (0.8 for 80%).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from common_check import load, report  # noqa: E402
from solution_ch02 import nw_share_of_90plus as reference  # noqa: E402

m = load(HERE, "ch02")
report([(f"nw_share_of_90plus({p}) = {reference(p):.4f}", abs(m.nw_share_of_90plus(p) - reference(p)) < 0.0005)
        for p in (1, 9, 10, 12)])
