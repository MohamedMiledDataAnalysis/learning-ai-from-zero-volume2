"""Print the Python extraction and analysis of both prospectuses as one JSON document,
for the R cross-language tests of Volume 2 Part E.

    python r/tests/helpers/python_extract.py > extract_reference.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

from tar_agent.tools.analyse import analyse_deal_terms  # noqa: E402
from tar_agent.tools.document import search_document  # noqa: E402
from tar_agent.tools.extract import extract_deal_terms  # noqa: E402
from tar_agent.tools.extract_sim import simulated_model_brain  # noqa: E402

DEALS = {"thames": ("data/prospectus/prospectus.pdf", "data/schemas/answers_thames.json"),
         "severn": ("data/prospectus_rmbs/prospectus.pdf", "data/schemas/answers_rmbs.json")}
out = {}
for name, (pdf, key_path) in DEALS.items():
    pdf = str(ROOT / pdf)
    key = json.loads((ROOT / key_path).read_text(encoding="utf-8"))
    both = extract_deal_terms(pdf, "both", simulated_model_brain(key))
    out[name] = {
        "rules": extract_deal_terms(pdf, "rules"),
        "both": both,
        "planted": extract_deal_terms(pdf, "model", simulated_model_brain(key, plant={"classes.B.margin": 0.018})),
        "analysis": analyse_deal_terms(both),
        "search": search_document(pdf, "trigger limit per cent", top_k=2),
    }
print(json.dumps(out, ensure_ascii=False))
