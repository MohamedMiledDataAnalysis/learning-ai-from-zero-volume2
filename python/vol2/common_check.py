"""Shared helper for the practical-task checkers of Volume 2, chapters 1 to 6.

Each checker imports the reader's file my_chNN.py from its chapter folder (or the reference
solution_chNN.py with --solution), runs the checks, and prints PASS or FAIL with the reason.
"""
import importlib.util
import sys
from pathlib import Path


def load(chapter_dir, chapter):
    name = f"solution_{chapter}.py" if "--solution" in sys.argv else f"my_{chapter}.py"
    path = Path(chapter_dir) / name
    if not path.exists():
        print(f"FAIL: create {path.name} in {Path(chapter_dir).name}/ first (see the practical task).")
        sys.exit(1)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(checks):
    """checks: list of (description, passed). Prints each and the verdict."""
    for text, ok in checks:
        print(f"  {'ok  ' if ok else 'FAIL'} {text}")
    passed = all(ok for _, ok in checks)
    print("PASS" if passed else "FAIL: reread the section given in the question.")
    return passed
