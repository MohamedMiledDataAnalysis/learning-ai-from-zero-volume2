"""Chapter 27: the Severn prospectus through the app's logic, with the rules layer and with both layers.

    python python/vol2/ch27/demo_severn.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402

doc = logic.sample_document("severn")
for layer in ("rules", "both"):
    out = logic.run_extraction(doc["path"], layer, "simulated", "severn")
    terms = out["terms"]
    result = logic.analysis(terms)
    print(f"Layer {layer} ({out['message']})")
    print(" ", logic.coverage_text(terms))
    print(" ", logic.key_score_text(terms, "severn"))
    checks = [c["result"] for c in logic.check_rows(result)]
    print(f"  Checks: {checks.count('pass')} pass, {checks.count('FAIL')} fail, {checks.count('not possible')} not possible")
    for row in logic.ce_rows(result):
        print(f"  Class {row['class']}: share {row['share of notes']}, subordination {row['subordination']}, "
              f"reserve {row['reserve support']}, CE {row['credit enhancement']}")
    print("  Waterfall:", {k: len(v) for k, v in logic.waterfall_steps(result).items()})
