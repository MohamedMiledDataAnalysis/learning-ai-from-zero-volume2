"""Print the Python agent's outputs as one JSON document, for the R cross-language tests.

    python r/tests/helpers/python_reference.py > reference.json
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

from tar_agent.registry import call_tool, tool_schemas  # noqa: E402
from tar_agent.tools.note import draft_surveillance_note  # noqa: E402
from tar_agent.tools.prospectus import search_prospectus  # noqa: E402
from tar_agent.tools.stratify import FIELDS  # noqa: E402

QUERIES = [
    "What is the limit for the 90+ day arrears ratio?", "servicer fee", "margin on Class B notes",
    "weighted average interest rate of the pool", "How much is the reserve fund at closing?",
    "definition of a defaulted loan", "Which loans were eligible?", "trustee fee",
]

out = {
    "schemas": tool_schemas(),
    "validate": json.loads(call_tool("validate_loan_tape", {})),
    "stratify": {f"{by}|{p}|{m}": json.loads(call_tool("stratify_pool", {"by": by, "period": p, "measure": m}))
                 for by in FIELDS for p in (0, 10, 12) for m in ("balance", "count", "balance_90plus")
                 if not (p == 0 and m == "balance_90plus")},
    "triggers": {str(p): json.loads(call_tool("run_trigger_tests", {"period": p})) for p in range(1, 13)},
    "notes": {str(p): draft_surveillance_note(p)["note_markdown"] for p in range(1, 13)},
    "search": {q: search_prospectus(q)["results"] for q in QUERIES},
    "errors": {
        "unknown_tool": json.loads(call_tool("run_trigger_test", {"period": 10})),
        "unknown_argument": json.loads(call_tool("run_trigger_tests", {"month": 10})),
        "bad_period": json.loads(call_tool("run_trigger_tests", {"period": 13})),
        "bad_by": json.loads(call_tool("stratify_pool", {"by": "colour"})),
    },
}
json.dump(out, sys.stdout, ensure_ascii=False)
