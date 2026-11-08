"""Chapter 11: what the model is told about one tool."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

import json

from tar_agent.registry import tool_schemas

schema = next(s for s in tool_schemas() if s["function"]["name"] == "run_trigger_tests")
print(json.dumps(schema, indent=2))
print(f"Tools described to the model: {len(tool_schemas())}")
