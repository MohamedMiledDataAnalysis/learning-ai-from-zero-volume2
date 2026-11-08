"""Chapter 28: does the Volume 1 default model treat North West borrowers differently?

Three logistic regressions, all trained on the same training loans and judged on the same test loans:
  A. with the north_west flag            (region used openly)
  B. without any location                (region removed)
  C. without north_west, with postcode areas  (region removed, but a proxy left in)
For each model we compare, at a threshold of 0.10, how often loans are flagged in the North West and elsewhere.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent
from tar_agent.tools.loan_tape import load_clean_tape  # noqa: E402

THRESHOLD = 0.10
loans = pd.read_csv("data/learning/loans_2026.csv")
loans["income_k"] = loans.annual_income / 1000
tape = load_clean_tape()[["loan_id", "postcode_area"]]
loans = loans.merge(tape, on="loan_id")
areas = pd.get_dummies(loans.postcode_area.replace("", "missing"), prefix="pc", dtype=float)
loans = pd.concat([loans, areas], axis=1)

BASE = ["credit_score", "ltv_original_pct", "income_k", "used"]
MODELS = {
    "A. with north_west": BASE + ["north_west"],
    "B. no location": BASE,
    "C. postcode areas": BASE + list(areas.columns),
}
train, test = loans[loans.set == "train"], loans[loans.set == "test"]
nw = test.north_west == 1

print("Actual bad rate in the test set: "
      f"North West {test[nw].bad.mean():.2%}, elsewhere {test[~nw].bad.mean():.2%}")
print()
print(f"{'Model':<22}{'recall':>8}{'flag NW':>9}{'flag rest':>11}{'FPR NW':>8}{'FPR rest':>10}")
for name, features in MODELS.items():
    # Model C has many columns: a light penalty (C=1) keeps its coefficients stable.
    model = LogisticRegression(C=np.inf if name[0] != "C" else 1.0, max_iter=100000, tol=1e-10)
    model.fit(train[features], train.bad)
    flagged = model.predict_proba(test[features])[:, 1] >= THRESHOLD
    bad = test.bad.to_numpy() == 1
    recall = (flagged & bad).sum() / bad.sum()
    flag_nw, flag_rest = flagged[nw.to_numpy()].mean(), flagged[~nw.to_numpy()].mean()
    # False positive rate: share of GOOD loans that the model flags anyway.
    fpr_nw = (flagged & ~bad & nw.to_numpy()).sum() / (~bad & nw.to_numpy()).sum()
    fpr_rest = (flagged & ~bad & ~nw.to_numpy()).sum() / (~bad & ~nw.to_numpy()).sum()
    print(f"{name:<22}{recall:>8.2%}{flag_nw:>9.2%}{flag_rest:>11.2%}{fpr_nw:>8.2%}{fpr_rest:>10.2%}")
    if name[0] == "C":
        coefs = pd.Series(model.coef_[0], index=features)
        top = coefs[[c for c in features if c.startswith("pc_")]].sort_values(ascending=False).head(5)
        print("\nModel C: the five postcode areas with the largest coefficients")
        nw_areas = {"pc_M", "pc_L", "pc_PR", "pc_BL", "pc_WA"}
        for col, value in top.items():
            print(f"  {col[3:]:<4} {value:7.3f}   {'North West' if col in nw_areas else 'other region'}")
