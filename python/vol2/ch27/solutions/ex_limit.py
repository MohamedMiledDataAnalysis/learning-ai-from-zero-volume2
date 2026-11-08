"""Exercise 27.5: do the limits read from the prospectus agree with the deal terms the generator used?"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import logic  # noqa: E402

terms = logic.run_extraction(str(logic.SAMPLES["thames"]["pdf"]), "rules", "simulated", "thames")["terms"]
read = logic.extracted_limits(terms)
truth = json.loads((logic.ROOT / "data" / "deal_terms.json").read_text(encoding="utf-8"))["triggers"]
print("90+ arrears limit  read:", read["arrears_90"], " deal terms:", truth["arrears_90_limit"],
      " agree:", read["arrears_90"] == truth["arrears_90_limit"])
schedule = [s["limit"] for s in read["cumulative_default"]]
print("Cumulative default read:", schedule, " deal terms:", [x[2] for x in truth["cum_default_schedule"]],
      " agree:", schedule == [x[2] for x in truth["cum_default_schedule"]])
