"""Chapter 5, applied example: how the scorer judges three answers to one question.

Run from the repository root:
    python python/vol2/ch05/score_examples.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))
from tar_agent.evaluate import load_questions, score_answer  # noqa: E402

q = next(x for x in load_questions() if x["id"] == "Q28")
print(f"{q['id']}: {q['question']}")
print(f"Expected: {json.dumps(q['expected'])}")
print()
for answer in [
    "The prospectus sets the limit at 1.25% (page 9).",
    "The limit for the 90+ day arrears ratio is 1.25%.",
    "The limit is 1.50% (page 9).",
]:
    ok, reason = score_answer(answer, q["expected"])
    print(f"{'CORRECT' if ok else 'WRONG  '}  {answer}")
    print(f"         reason: {reason}")
