"""Check the chapter 5 practical task: python python/vol2/ch05/check_ch05.py

Your file my_ch05.py must define tools_used(question), returning the tool names of a rules-mode run.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from common_check import load, report  # noqa: E402

m = load(HERE, "ch05")
cases = {"Run the trigger tests for period 10.": ["run_trigger_tests"],
         "According to the prospectus, what is the servicer fee?": ["search_prospectus"],
         "What is the weather in London?": []}
report([(f"{q} -> {t}", m.tools_used(q) == t) for q, t in cases.items()])
