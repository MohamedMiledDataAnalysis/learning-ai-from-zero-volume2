"""Chapter 28, exercise 28.4: model A at three thresholds — how the gap between regions changes."""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

loans = pd.read_csv("data/learning/loans_2026.csv")
loans["income_k"] = loans.annual_income / 1000
features = ["credit_score", "ltv_original_pct", "income_k", "used", "north_west"]
train, test = loans[loans.set == "train"], loans[loans.set == "test"]
model = LogisticRegression(C=np.inf, max_iter=100000, tol=1e-10).fit(train[features], train.bad)
p = model.predict_proba(test[features])[:, 1]
bad, nw = test.bad.to_numpy() == 1, test.north_west.to_numpy() == 1

print(f"{'threshold':>9}{'recall':>9}{'FPR NW':>9}{'FPR rest':>10}")
for th in (0.10, 0.20, 0.30):
    flagged = p >= th
    recall = (flagged & bad).sum() / bad.sum()
    fpr_nw = (flagged & ~bad & nw).sum() / (~bad & nw).sum()
    fpr_rest = (flagged & ~bad & ~nw).sum() / (~bad & ~nw).sum()
    print(f"{th:>9.2f}{recall:>9.2%}{fpr_nw:>9.2%}{fpr_rest:>10.2%}")
