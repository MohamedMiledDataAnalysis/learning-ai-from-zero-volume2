"""Chapter 27: ask a question about a sample prospectus, as the Ask tab of the Dash app does.

    python python/vol2/ch27/ask_prospectus.py --deal severn --mode rules
    python python/vol2/ch27/ask_prospectus.py --deal severn --mode replay
    python python/vol2/ch27/ask_prospectus.py --deal severn --mode record     # needs Ollama

record saves the pinned model's reply to python/recordings/vol2-partE-ask.jsonl, which the app's
replay mode plays back for this question about Severn only.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402

parser = argparse.ArgumentParser()
parser.add_argument("--deal", choices=sorted(logic.SAMPLES), default=logic.ASK_RECORDED["sample"])
parser.add_argument("--mode", choices=["rules", "replay", "live", "record"], default="rules")
parser.add_argument("--question", default=logic.ASK_RECORDED["question"])
args = parser.parse_args()

if args.mode == "record" and (args.deal, args.question) != (logic.ASK_RECORDED["sample"], logic.ASK_RECORDED["question"]):
    sys.exit("record only the question the app replays: --deal severn and the default question")
if args.mode == "replay" and not (logic.ASK_RECORDING.exists() and logic.ASK_RECORDING.stat().st_size):
    print(logic.PENDING)                         # the book prints this line until the recording exists
    sys.exit(0)
out = logic.answer_question(str(logic.SAMPLES[args.deal]["pdf"]), args.question, args.mode, sample=args.deal)
print("Question:", args.question)
print("Pages of the passages:", ", ".join(str(p["page"]) for p in out["passages"]))
print("Answer:", out["answer"])
