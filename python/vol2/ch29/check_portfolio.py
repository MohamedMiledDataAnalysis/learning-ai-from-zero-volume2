"""Chapter 29: check that a portfolio project folder has what a reviewer looks for first.

Run from the repository root:
    python python/vol2/ch29/check_portfolio.py python/vol2/ch29/example_portfolio
"""

import sys
from pathlib import Path

SECTIONS = ["## Problem", "## Data", "## How to run", "## Results", "## Limits"]
folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
checks = []

readme = folder / "README.md"
text = readme.read_text(encoding="utf-8") if readme.exists() else ""
checks.append(("README.md exists", readme.exists()))
for s in SECTIONS:
    checks.append((f"README has a '{s[3:]}' section", s in text))
req = folder / "requirements.txt"                      # comment lines (#) and blank lines are skipped
pins = [ln for ln in req.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")] if req.exists() else []
checks.append(("requirements.txt pins versions (==)", bool(pins) and all("==" in ln for ln in pins)))
tests = list((folder / "tests").glob("test_*.py")) if (folder / "tests").exists() else []
checks.append(("at least one test file in tests/", bool(tests)))
big = [p.name for p in folder.rglob("*") if p.is_file() and p.stat().st_size > 50_000_000]
checks.append(("no file larger than 50 MB", not big))
secrets = [p.name for p in folder.rglob("*") if p.is_file() and p.name in (".env", "credentials.json")]
checks.append(("no secrets file (.env, credentials.json)", not secrets))

for name, ok in checks:
    print(f"[{'ok' if ok else '  '}] {name}")
print(f"{sum(ok for _, ok in checks)}/{len(checks)} checks passed")
