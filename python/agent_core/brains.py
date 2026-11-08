"""Brains: the part of the agent that decides the next step.

Every brain has one method, next(memory, schemas), and returns a dict:

    {"content": "text for the user", "tool_calls": [{"name": ..., "arguments": {...}}]}

An empty tool_calls list means the brain has given its final answer.

RuleBrain       plain if/else rules written by you: no AI, fully predictable
OllamaBrain     a local language model served by Ollama (free, runs on your computer)
RecordingBrain  wraps another brain and saves every reply to a file
ReplayBrain     plays back a saved file: the same replies, in the same order, every time
"""

import json
from pathlib import Path

DEFAULT_MODEL = "qwen2.5:7b"     # pinned: the book's transcripts were recorded with this model
DEFAULT_OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 8192}   # num_ctx: fixed context window


class RuleBrain:
    """A 'fake brain': a Python function that looks at the memory and decides."""

    def __init__(self, rules):
        self.rules = rules

    def next(self, memory, schemas):
        return self.rules(memory)


class OllamaBrain:
    """A real language model running in Ollama at http://localhost:11434."""

    def __init__(self, model=DEFAULT_MODEL, options=None, host=None):
        import ollama                       # imported here so the other brains work without it
        self.client = ollama.Client(host=host) if host else ollama.Client()
        self.model = model
        self.options = options or DEFAULT_OPTIONS

    def next(self, memory, schemas):
        response = self.client.chat(model=self.model, messages=memory, tools=schemas, options=self.options)
        message = response["message"]
        calls = []
        for tc in message.get("tool_calls") or []:
            args = tc["function"]["arguments"]
            calls.append({"name": tc["function"]["name"],
                          "arguments": json.loads(args) if isinstance(args, str) else dict(args)})
        return {"content": message.get("content") or "", "tool_calls": calls}


class RecordingBrain:
    """Passes each call to another brain and saves its replies to a JSON Lines file.

    The file is written only after a reply has arrived, and replaced in one step, so a failed run
    (for example with Ollama not running) never leaves an empty or half-written recording behind.
    """

    def __init__(self, inner, path):
        self.inner, self.path = inner, Path(path)
        self.replies = []

    def next(self, memory, schemas):
        reply = self.inner.next(memory, schemas)
        self.replies.append(reply)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        partial = self.path.with_name(self.path.name + ".partial")
        partial.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self.replies),
                           encoding="utf-8")
        partial.replace(self.path)
        return reply


class ReplayBrain:
    """Plays back a recording made by RecordingBrain."""

    def __init__(self, path):
        self.path = Path(path)
        if not recording_ready(self.path):
            raise FileNotFoundError(f"no recording at {self.path}: run once with --mode record (needs Ollama)")
        self.replies = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]
        self.position = 0

    def next(self, memory, schemas):
        if self.position >= len(self.replies):
            raise RuntimeError("the recording has no more replies: the run has gone differently from the recording")
        reply = self.replies[self.position]
        self.position += 1
        return reply


def recording_ready(path):
    """True when a recording exists and is not empty."""
    path = Path(path)
    return path.exists() and path.stat().st_size > 0


def make_brain(mode, recording, rules=None, model=DEFAULT_MODEL):
    """Choose a brain from the command line: rules, live, record or replay."""
    if mode == "rules":
        return RuleBrain(rules)
    if mode == "live":
        return OllamaBrain(model)
    if mode == "record":
        return RecordingBrain(OllamaBrain(model), recording)
    if mode == "replay":
        return ReplayBrain(recording)
    raise ValueError("mode must be rules, live, record or replay")
