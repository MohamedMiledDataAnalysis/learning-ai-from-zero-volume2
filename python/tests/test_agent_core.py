"""Tests for the shared agent loop and the brains."""

import json

from agent_core import fake_ollama
from agent_core.brains import OllamaBrain, RecordingBrain, ReplayBrain, RuleBrain
from agent_core.loop import run_agent

SCHEMAS = [{"type": "function", "function": {"name": "add", "description": "Add two numbers.",
            "parameters": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                           "required": ["a", "b"]}}}]


def call_tool(name, args):
    if name != "add":
        return json.dumps({"error": f"unknown tool '{name}'"})
    return json.dumps({"result": args["a"] + args["b"]})


def adding_rules(memory):
    last = memory[-1]
    if last["role"] == "user":
        return {"content": "", "tool_calls": [{"name": "add", "arguments": {"a": 2, "b": 3}}]}
    return {"content": f"The total is {json.loads(last['content'])['result']}.", "tool_calls": []}


def test_loop_runs_tool_then_answers():
    out = run_agent("Add 2 and 3.", RuleBrain(adding_rules), SCHEMAS, call_tool, "You add numbers.", log=lambda m: None)
    assert out["answer"] == "The total is 5."
    assert [s["type"] for s in out["steps"]] == ["tool", "answer"]
    assert [m["role"] for m in out["memory"]] == ["system", "user", "assistant", "tool", "assistant"]


def test_step_limit_stops_a_brain_that_never_answers():
    loop_forever = RuleBrain(lambda m: {"content": "", "tool_calls": [{"name": "add", "arguments": {"a": 1, "b": 1}}]})
    out = run_agent("Add.", loop_forever, SCHEMAS, call_tool, "", max_steps=3, log=lambda m: None)
    assert out["stopped_because"] == "step limit" and out["answer"] is None


def test_record_then_replay_gives_identical_runs(tmp_path):
    path = tmp_path / "rec.jsonl"
    first = run_agent("Add 2 and 3.", RecordingBrain(RuleBrain(adding_rules), path), SCHEMAS, call_tool, "",
                      log=lambda m: None)
    second = run_agent("Add 2 and 3.", ReplayBrain(path), SCHEMAS, call_tool, "", log=lambda m: None)
    assert first["memory"] == second["memory"]


def test_ollama_brain_speaks_the_ollama_http_format():
    script = [{"content": "", "tool_calls": [{"name": "add", "arguments": {"a": 2, "b": 3}}]},
              {"content": "The total is 5.", "tool_calls": []}]
    server, url, received = fake_ollama.start(script)
    try:
        out = run_agent("Add 2 and 3.", OllamaBrain(host=url), SCHEMAS, call_tool, "You add numbers.",
                        log=lambda m: None)
    finally:
        server.shutdown()
    assert out["answer"] == "The total is 5."
    assert received[0]["model"] == "qwen2.5:7b"
    assert received[0]["options"] == {"temperature": 0, "seed": 42, "num_ctx": 8192}
    assert received[0]["tools"][0]["function"]["name"] == "add"
    assert received[1]["messages"][-1] == {"role": "tool", "content": '{"result": 5}', "tool_name": "add"}


def test_failed_recording_leaves_no_file(tmp_path):
    class Broken:
        def next(self, memory, schemas):
            raise ConnectionError("Ollama is not running")
    path = tmp_path / "rec.jsonl"
    brain = RecordingBrain(Broken(), path)
    try:
        brain.next([], SCHEMAS)
    except ConnectionError:
        pass
    assert not path.exists() and not (tmp_path / "rec.jsonl.partial").exists()


def test_empty_recording_counts_as_missing(tmp_path):
    from agent_core.brains import recording_ready
    path = tmp_path / "rec.jsonl"
    path.write_text("", encoding="utf-8")
    assert not recording_ready(path)
    try:
        ReplayBrain(path)
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised
