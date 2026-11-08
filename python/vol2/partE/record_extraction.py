"""Run the model layer of the extraction on one of the book's prospectuses.

    python python/vol2/partE/record_extraction.py --deal severn --mode replay
    python python/vol2/partE/record_extraction.py --deal severn --mode record     # needs Ollama

Modes: simulated (a stand-in built from the answer key, labelled as such), replay (the
recorded replies of the pinned model), live and record (Ollama with qwen2.5:7b).
Prints the coverage, the score against the answer key and the values that failed grounding.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

from agent_core.brains import make_brain  # noqa: E402
from tar_agent.tools.extract import extract_deal_terms, score_against_key  # noqa: E402
from tar_agent.tools.extract_sim import simulated_model_brain  # noqa: E402

DEALS = {
    "thames": (ROOT / "data" / "prospectus" / "prospectus.pdf", ROOT / "data" / "schemas" / "answers_thames.json"),
    "severn": (ROOT / "data" / "prospectus_rmbs" / "prospectus.pdf", ROOT / "data" / "schemas" / "answers_rmbs.json"),
}

parser = argparse.ArgumentParser()
parser.add_argument("--deal", choices=sorted(DEALS), default="severn")
parser.add_argument("--mode", choices=["simulated", "replay", "live", "record"], default="replay")
args = parser.parse_args()

pdf, key_path = DEALS[args.deal]
key = json.loads(key_path.read_text(encoding="utf-8"))
recording = ROOT / "python" / "recordings" / f"vol2-partE-extract-{args.deal}.jsonl"
if args.mode == "replay" and not (recording.exists() and recording.stat().st_size):
    print("[Recording pending: run python record_all.py with Ollama installed, then rebuild]")
    sys.exit(0)
brain = simulated_model_brain(key) if args.mode == "simulated" else make_brain(args.mode, recording)

terms = extract_deal_terms(pdf, layer="both", brain=brain)
score = score_against_key(terms, key)
label = "simulated model (not a language model)" if args.mode == "simulated" else f"model, {args.mode} mode"
print(f"Deal: {args.deal}   layers: rules + {label}")
print(f"Schema fields found: {terms['coverage']['found']} of {terms['coverage']['schema_fields']}")
print(f"Answer key: {score['found']} of {score['fields']} values found, {score['correct']} correct")
print(f"Sections: " + ", ".join(f"{s['section']} {'ok' if s['ok'] else 'FAILED'}" for s in terms["model_log"]))
print(f"Values that failed the page grounding check: {terms['ungrounded'] or 'none'}")
