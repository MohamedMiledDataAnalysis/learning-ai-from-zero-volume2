"""Chapter 11: what the model reads back when its tool call is wrong."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

from tar_agent.registry import call_tool

print(call_tool("run_trigger_test", {"period": 10}))
print(call_tool("run_trigger_tests", {"month": 10}))
print(call_tool("run_trigger_tests", {"period": 13}))
print(call_tool("run_trigger_tests", "{period: 10}"))
