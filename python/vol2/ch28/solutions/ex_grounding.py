"""Chapter 28, exercise 28.5: the grounding check on three test answers (made up for the exercise)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # tar_agent, agent_core
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # guards.py
from guards import grounding_check  # noqa: E402
from tar_agent.registry import call_tool  # noqa: E402

question = "What was the cumulative default ratio in December 2026?"
results = [call_tool("run_trigger_tests", {"period": 12})]
answers = {
    "a": "In period 12 the cumulative default ratio is 0.86% against a limit of 2.00%.",
    "b": "In period 12 the cumulative default ratio is 0.86%, which is 43% of the limit.",
    "c": "In period 12 the cumulative default ratio is 0.68% against a limit of 2.00%.",
}
for name, answer in answers.items():
    print(f"{name}: ungrounded = {grounding_check(answer, question, results)}")
