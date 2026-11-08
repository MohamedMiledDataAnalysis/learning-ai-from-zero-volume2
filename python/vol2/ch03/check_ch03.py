"""Check the chapter 3 practical task: python python/vol2/ch03/check_ch03.py

Your file my_ch03.py must define my_plan(period), returning a list of steps. The plan must include
every checklist item, use only the five tool names, and add at least one step of your own.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1]))
from common_check import load, report  # noqa: E402
from tar_agent.agentic import CHECKLIST, check_plan  # noqa: E402
from tar_agent.registry import TOOLS  # noqa: E402

m = load(HERE, "ch03")
plan = m.my_plan(11)
_, missing, rejected = check_plan(plan, 11)
report([
    ("the plan is a list of steps with a 'tool' each", isinstance(plan, list) and all("tool" in s for s in plan)),
    ("only the five tools are used", all(s["tool"] in TOOLS for s in plan)),
    ("no checklist item is missing", not missing),
    ("no step is rejected (every step is for period 11)", not rejected),
    ("at least one step beyond the checklist", len(plan) > len(CHECKLIST)),
])
