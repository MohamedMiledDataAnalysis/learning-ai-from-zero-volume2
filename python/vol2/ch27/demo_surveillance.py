"""Chapter 27: the Thames reports tested against the limits read from the prospectus (rules layer)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402

terms = logic.run_extraction(str(logic.SAMPLES["thames"]["pdf"]), "rules", "simulated", "thames")["terms"]
print("Limits read from the prospectus:", logic.extracted_limits(terms))
for row in logic.surveillance(terms, use_thames_data=True)["rows"][8:]:
    print(row)
