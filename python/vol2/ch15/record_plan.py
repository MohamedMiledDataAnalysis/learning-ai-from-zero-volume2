"""Chapter 15: record (or replay) a live model writing the monthly plan, then check it against the checklist.

    python python/vol2/ch15/record_plan.py record       record with Ollama
    python python/vol2/ch15/record_plan.py     replay the recording
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from agent_core.brains import make_brain  # noqa: E402
from tar_agent.agentic import run_surveillance  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "replay"     # record only when asked: "record"
recording = Path(__file__).resolve().parents[2] / "recordings" / "vol2_ch15_plan.jsonl"
if mode == "replay" and not (recording.exists() and recording.stat().st_size):
    print("[Recording pending: run python record_all.py with Ollama installed, then rebuild]")
    sys.exit(0)
with tempfile.TemporaryDirectory() as folder:
    r = run_surveillance(10, plan_source="model", brain=make_brain(mode, recording),
                         memory_dir=Path(folder) / "m", out_dir=Path(folder) / "o", approve=False)
print("Steps missing from the model's plan:", [m["tool"] for m in r["missing_from_plan"]] or "none")
