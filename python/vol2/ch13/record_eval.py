"""Chapter 13: score the live model on the 40 questions (record) or replay the recorded run.

    python python/vol2/ch13/record_eval.py record       record with Ollama: one recording per question
    python python/vol2/ch13/record_eval.py     score the recorded replies
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.evaluate import RECORDINGS, run_evaluation  # noqa: E402

mode = sys.argv[1] if len(sys.argv) > 1 else "replay"     # record only when asked: "record"
if mode == "replay" and not ((RECORDINGS / "Q01.jsonl").exists() and (RECORDINGS / "Q01.jsonl").stat().st_size):
    print("[Recording pending: run python record_all.py with Ollama installed, then rebuild]")
    sys.exit(0)
out = run_evaluation(mode)
for r in out["results"]:
    if not r["correct"]:
        print(f"{r['id']}  WRONG  {r['reason']}  tools used: {r['tools_used']}")
print(f"Score (qwen2.5:7b, {mode}): {out['score']} / {out['out_of']}")
