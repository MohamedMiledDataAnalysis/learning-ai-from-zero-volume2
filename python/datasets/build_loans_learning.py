"""Build the learning dataset used in Volume 1, Part II (chapters 9 to 12).

Run from the repository root:

    python python/datasets/build_loans_learning.py

It writes three files to data/learning/:
- loans_2026.csv          one row per loan: features at the cut-off date, the 2026 outcome, train/test set
- kmeans_start_rows.csv   the rows used as starting centres for k-means (chapter 11)
- nn_initial_weights.json the starting weights of the small neural network (chapter 12)

Python and R both read these files, so both languages work on exactly the same
rows, the same split and the same starting points.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
from tar_agent.tools.loan_tape import load_clean_tape  # noqa: E402

OUT = REPO / "data" / "learning"
SEED = 2026


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tape = load_clean_tape()
    tape = tape[tape.credit_score.notna()].copy()          # 1 loan has no usable credit score: left out

    # The outcome: did the loan reach 3 or more instalments in arrears, or default, during 2026?
    perf = pd.read_csv(REPO / "data" / "loan_performance.csv")
    perf["bad_month"] = (perf.instalments_in_arrears >= 3) | (perf.status == "Defaulted")
    bad = perf.groupby("loan_id").bad_month.any().astype(int)

    df = pd.DataFrame({
        "loan_id": tape.loan_id,
        "credit_score": tape.credit_score.astype(int),
        "interest_rate_pct": tape.interest_rate_pct,
        "ltv_original_pct": tape.ltv_original_pct,
        "annual_income": tape.annual_income,
        "original_balance": tape.original_balance,
        "remaining_term_months": tape.remaining_term_months,
        "used": (tape.vehicle_type == "Used").astype(int),
        "pcp": (tape["product"] == "PCP").astype(int),
        "north_west": (tape.region == "North West").astype(int),
        "region": tape.region,
        "bad": tape.loan_id.map(bad).astype(int),
    }).sort_values("loan_id").reset_index(drop=True)

    # Train/test split, 70% / 30%, done separately for good and bad loans so both sets keep the same mix.
    rng = np.random.default_rng(SEED)
    df["set"] = "train"
    for label in (0, 1):
        idx = df.index[df.bad == label].to_numpy()
        test = rng.choice(idx, size=round(len(idx) * 0.30), replace=False)
        df.loc[test, "set"] = "test"
    df.to_csv(OUT / "loans_2026.csv", index=False)

    # Starting centres for k-means: 8 row numbers (1-based, so R and Python agree), chosen at random once.
    rows = rng.choice(len(df), size=8, replace=False) + 1
    pd.DataFrame({"row": rows}).to_csv(OUT / "kmeans_start_rows.csv", index=False)

    # Starting weights of the network in chapter 12: 4 inputs -> 3 hidden neurons -> 1 output.
    w = {"W1": rng.normal(0, 0.5, (4, 3)).round(4).tolist(), "b1": [0.0, 0.0, 0.0],
         "W2": rng.normal(0, 0.5, (3, 1)).round(4).tolist(), "b2": [0.0]}
    (OUT / "nn_initial_weights.json").write_text(json.dumps(w, indent=2))

    tr, te = df[df.set == "train"], df[df.set == "test"]
    print(f"loans: {len(df):,}  bad: {df.bad.sum()} ({df.bad.mean():.2%})")
    print(f"train: {len(tr):,} loans, {tr.bad.sum()} bad   test: {len(te):,} loans, {te.bad.sum()} bad")


if __name__ == "__main__":
    main()
