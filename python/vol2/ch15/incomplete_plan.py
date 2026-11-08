"""Chapter 15: a plan that forgets three checks is completed from the analyst's checklist.

The 'model' here is a RuleBrain that returns a hand-written incomplete plan, so the
example is reproducible. A live model can make the same omission; the checklist catches it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

import json
import tempfile
from pathlib import Path

from agent_core.brains import RuleBrain
from tar_agent.agentic import run_surveillance

incomplete = [{"tool": "run_trigger_tests", "arguments": {"period": 10}, "why": "check the triggers"}]
brain = RuleBrain(lambda memory: {"content": json.dumps(incomplete), "tool_calls": []})
with tempfile.TemporaryDirectory() as folder:
    r = run_surveillance(10, plan_source="model", brain=brain, memory_dir=Path(folder) / "m",
                         out_dir=Path(folder) / "o", approve=False)
print("Missing from the plan:")
for m in r["missing_from_plan"]:
    print("  -", m["tool"], m.get("arguments", {}))
