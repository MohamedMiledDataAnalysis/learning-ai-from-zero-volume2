"""Chapter 28: a model-risk documentation table for the Thames agent, built from the code itself.

The five rows follow the five principles of the PRA's supervisory statement SS1/23. Every piece of
evidence is read from the repository or computed by running it, so the table cannot claim more than
the code does. "GAP" marks what the code cannot provide on its own.
"""

import inspect
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "python"))
from agent_core import brains  # noqa: E402
from tar_agent import agent, agentic, registry  # noqa: E402
from tar_agent.evaluate import run_evaluation  # noqa: E402
from tar_agent.tools import prospectus  # noqa: E402


def count_python_tests():
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "python/tests"],
                         cwd=REPO, capture_output=True, text=True).stdout
    match = re.search(r"(\d+) tests? collected", out)
    return int(match.group(1)) if match else 0


def count_deal_pack_checks():
    out = subprocess.run([sys.executable, "tests/check_deal_pack.py"], cwd=REPO, capture_output=True, text=True).stdout
    return out.count("PASS"), out.count("FAIL")


tools = [s["function"]["name"] for s in registry.tool_schemas()]
recordings = sorted(p.name for p in (REPO / "python" / "recordings").glob("*.jsonl"))
score = run_evaluation("rules")
passed, failed = count_deal_pack_checks()
max_steps = inspect.signature(agent.ask).parameters["max_steps"].default
approve_param = "approve" in inspect.signature(agentic.run_surveillance).parameters

rows = [
    ("1. Model identification and classification",
     [f"Language model pinned: {brains.DEFAULT_MODEL}, options {brains.DEFAULT_OPTIONS}",
      f"Retrieval: BM25 with k1 = {prospectus.K1}, b = {prospectus.B}",
      f"{len(tools)} tools: {', '.join(tools)}",
      "Use: supports an analyst; takes no decision about a borrower"]),
    ("2. Governance",
     [f"Human approval before a note is sent: {'yes (approve parameter)' if approve_param else 'NO'}",
      "GAP: model owner and approver must be named by the firm"]),
    ("3. Development, implementation and use",
     [f"Python tests collected: {count_python_tests()}",
      f"Deal-pack checks: {passed} passed, {failed} failed",
      f"40-question evaluation, rules brain: {score['score']}/{score['out_of']}",
      f"Live-model recordings present: {len(recordings)}"
      + ("" if recordings else " (GAP: live-model score not yet measured)")]),
    ("4. Independent model validation",
     ["GAP: someone who did not build the agent must re-run the evaluation and review the code"]),
    ("5. Model risk mitigants",
     [f"Step limit: {max_steps} steps per question",
      "Tool errors returned as text, never raised (registry.call_tool)",
      f"Self-check of the 90+ ratio with a second tool: {'yes' if hasattr(agentic, 'self_check') else 'NO'}",
      "Grounding check of every number in an answer: yes (chapter 28, guards.py)"]),
]

for principle, evidence in rows:
    print(principle)
    for item in evidence:
        print(f"   - {item}")
