"""Chapter 13: five of the forty questions, with their expected answers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.evaluate import load_questions

for q in load_questions():
    if q["id"] in ("Q01", "Q13", "Q21", "Q28", "Q40"):
        print(q["id"], q["question"])
        print("    expected:", q["expected"], " tools:", q["tools"])
