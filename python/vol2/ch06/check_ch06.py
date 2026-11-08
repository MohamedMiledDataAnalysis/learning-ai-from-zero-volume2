"""Check the chapter 6 practical task: python python/vol2/ch06/check_ch06.py

Your file my_ch06.py must define call_over_mcp(name, arguments), returning the tool's result as a dictionary
(or {"error": ...} when the server refuses).
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common_check import load, report  # noqa: E402

m = load(HERE, "ch06")
fee = m.call_over_mcp("search_prospectus", {"query": "servicer fee", "top_k": 1})
trig = m.call_over_mcp("run_trigger_tests", {"period": 10})
refused = m.call_over_mcp("validate_loan_tape", {})
report([
    ("search_prospectus finds page 8", fee.get("results", [{}])[0].get("page") == 8),
    ("run_trigger_tests returns period 10", trig.get("period") == 10),
    ("validate_loan_tape is refused", "error" in refused),
])
