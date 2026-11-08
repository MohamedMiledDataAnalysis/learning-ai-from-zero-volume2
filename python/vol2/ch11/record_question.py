"""Chapter 11: record (or replay) the live model answering one question.

    python python/vol2/ch11/record_question.py            replay the recording (the default; used by the book)
    python python/vol2/ch11/record_question.py record    record with Ollama (used by record_all.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tar_agent.agent import RECORDINGS, ask  # noqa: E402

QUESTION = "Which region holds most of the 90+ day arrears in October 2026, and is any trigger breached?"
mode = sys.argv[1] if len(sys.argv) > 1 else "replay"     # record only when asked: "record"
recording = RECORDINGS / "vol2_ch11_question.jsonl"
if mode == "replay" and not (recording.exists() and recording.stat().st_size):
    print("[Recording pending: run python record_all.py with Ollama installed, then rebuild]")
    sys.exit(0)
run = ask(QUESTION, mode, recording)
print()
print("Answer:", run["answer"])
