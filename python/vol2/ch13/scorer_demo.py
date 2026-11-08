"""Chapter 13: the scorer on right and wrong answers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.evaluate import score_answer

expected = {"kind": "number", "value": 1.25, "tolerance": 0, "page": 9}
for answer in ["The limit is 1.25% (page 9).", "The limit is 1.25%.", "The limit is 1.5% (page 9).",
               "The limit is 1.25% (page 8)."]:
    ok, reason = score_answer(answer, expected)
    print(f"{'RIGHT' if ok else 'WRONG'}  {answer:<32} {reason}")
