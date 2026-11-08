"""Exercise 27.4: plant a wrong Class C margin and see which row turns red."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import logic  # noqa: E402
from tar_agent.tools.extract import extract_deal_terms  # noqa: E402
from tar_agent.tools.extract_sim import simulated_model_brain  # noqa: E402

key = json.loads(logic.SAMPLES["severn"]["key"].read_text(encoding="utf-8"))
brain = simulated_model_brain(key, plant={"classes.C.margin": 0.02})
terms = extract_deal_terms(str(logic.SAMPLES["severn"]["pdf"]), layer="model", brain=brain)
print("Model layer:", logic.SIMULATED_LABEL, "- one value planted wrong")
print(logic.coverage_text(terms))
for row in logic.terms_rows(terms):
    if row["grounded"] == "NOT grounded":
        print(row["field"], row["value"], "page", row["page"], "-", row["grounded"])
print("Checks:", [c["result"] for c in logic.check_rows(logic.analysis(terms))])
