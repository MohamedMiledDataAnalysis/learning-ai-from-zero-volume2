"""Chapter 15: three months of agentic surveillance (9 and 10 approved, 11 declined)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # lets Python find tar_agent and agent_core

import tempfile
from pathlib import Path

from tar_agent.agentic import run_surveillance

with tempfile.TemporaryDirectory() as folder:
    folder = Path(folder)
    for period, approve in [(9, True), (10, True), (11, False)]:
        r = run_surveillance(period, memory_dir=folder / "memory", out_dir=folder / "out", approve=approve)
        for line in r["changes"]:
            print("  memory:", line)
        print()
