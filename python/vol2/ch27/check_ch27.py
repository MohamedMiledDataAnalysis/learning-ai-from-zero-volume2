"""Check your answer to the practical task of chapter 27 (my_answer.py)."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402

module = sys.argv[1] if len(sys.argv) > 1 else "my_answer"
answer = importlib.import_module(module)
terms = logic.run_extraction(str(logic.SAMPLES["severn"]["pdf"]), "both", "simulated", "severn")["terms"]
result = logic.analysis(terms)
cases = {"A": "13.955%", "B": "9.955%", "Z": "0.000%"}
score = 0
for name, expected in cases.items():
    got = answer.ce_of_class(result, name)
    ok = got == expected
    score += ok
    print(f"Class {name}: expected {expected}, got {got!r} - {'correct' if ok else 'not yet'}")
print(f"Score: {score} of {len(cases)}")
