"""Chapter 29: which skills from this book each role uses most (X = core skill for the role)."""

import csv
from pathlib import Path

ROLES = ["ai_engineer", "data_scientist", "ml_engineer", "analytics_engineer", "surveillance_analyst",
         "model_validator"]
SHORT = ["AI eng", "Data sci", "ML eng", "Analytics", "Surveil.", "Validator"]

with open(Path(__file__).with_name("skills.csv"), encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
W = [9, 9, 9, 10, 9, 10]                       # column widths: each label keeps at least one space before it
print(f"{'Skill':<31}" + "".join(f"{s:>{w}}" for s, w in zip(SHORT, W)))
for r in rows:
    print(f"{r['skill']:<31}" + "".join(f"{'X' if r[role] == '1' else '.':>{w}}" for role, w in zip(ROLES, W)))
print(f"{'Core skills per role':<31}" + "".join(f"{sum(r[role] == '1' for r in rows):>{w}}" for role, w in zip(ROLES, W)))
