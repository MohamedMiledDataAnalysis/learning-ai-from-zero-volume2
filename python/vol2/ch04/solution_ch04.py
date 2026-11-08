"""Reference solution, chapter 4 practical task: a wider list of injection patterns."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guardrails import INJECTION_PATTERNS  # noqa: E402

PATTERNS = INJECTION_PATTERNS + [
    r"\bdisregard (the|all|any) (above|previous|earlier)\b",
    r"\bforget (everything|all) (you|that)\b",
    r"\bnew instructions?\b",
]
