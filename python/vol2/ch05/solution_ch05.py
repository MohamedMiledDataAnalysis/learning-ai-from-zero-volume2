"""Reference solution, chapter 5 practical task: the list of tools a run used, read from its trace."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tracing import trace_records  # noqa: E402


def tools_used(question):
    return [r["tool"] for r in trace_records(question) if r.get("type") == "tool"]
