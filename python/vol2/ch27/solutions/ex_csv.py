"""Exercise 27.3: a CSV export of the terms table (a third download button would call this)."""

import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import logic  # noqa: E402


def export_csv(terms):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["field", "value", "page", "source", "grounded", "quote"])
    writer.writeheader()
    writer.writerows(logic.terms_rows(terms))
    return buffer.getvalue()


terms = logic.run_extraction(str(logic.SAMPLES["thames"]["pdf"]), "rules", "simulated", "thames")["terms"]
text = export_csv(terms)
print(f"{len(text.splitlines()) - 1} rows")
print("\n".join(text.splitlines()[:4]))
