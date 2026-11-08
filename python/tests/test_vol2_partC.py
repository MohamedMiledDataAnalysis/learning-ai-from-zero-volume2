"""Tests for Volume 2 Part C: the agent, the evaluation, the export and the agentic cycle."""

import json

import openpyxl
import pytest

from agent_core.brains import RuleBrain
from tar_agent import agentic
from tar_agent.agent import ask, choose_tool, find_period, main as agent_main
from tar_agent.evaluate import QUESTIONS_FILE, build_questions, load_questions, run_evaluation, score_answer
from tar_agent.export import export_monthly_pack

QUIET = dict(log=lambda m: None)


# ---------------------------------------------------------------- the agent (chapter 11)
def test_agent_answers_the_trigger_question_end_to_end():
    run = ask("Run the trigger tests for period 10.", "rules", None, **QUIET)
    assert [s["type"] for s in run["steps"]] == ["tool", "answer"]
    assert "1.32% against a limit of 1.25% (breached)" in run["answer"]
    assert "Principal is paid sequentially" in run["answer"]


@pytest.mark.parametrize("text, period", [("period 7", 7), ("in October 2026", 10), ("at the cut-off date", 0),
                                          ("this month", None)])
def test_find_period(text, period):
    assert find_period(text) == period


def test_rule_order_sends_pcp_question_to_stratify():
    name, args = choose_tool("What share of the pool balance at the cut-off date is PCP?")
    assert name == "stratify_pool" and args == {"by": "product", "period": 0, "measure": "balance"}


def test_unknown_question_gets_a_polite_refusal():
    run = ask("What is the weather in London?", "rules", None, **QUIET)
    assert run["answer"].startswith("I can only answer")


def test_replay_without_recording_prints_the_pending_line(capsys, tmp_path):
    agent_main(["Run the trigger tests for period 10.", "--mode", "replay", "--recording", str(tmp_path / "x.jsonl")])
    assert capsys.readouterr().out.strip() == \
        "[Recording pending: run python record_all.py with Ollama installed, then rebuild]"


# ---------------------------------------------------------------- evaluation (chapter 13)
def test_question_file_is_up_to_date_with_the_data():
    assert load_questions() == json.loads(json.dumps(build_questions()))
    assert len(load_questions(QUESTIONS_FILE)) == 40


def test_rule_brain_scores_40_out_of_40():
    out = run_evaluation("rules")
    assert out["score"] == 40
    assert all(r["right_tools"] for r in out["results"])


@pytest.mark.parametrize("answer, expected, ok", [
    ("The ratio is 1.32%.", {"kind": "number", "value": 1.321, "tolerance": 0.006}, True),
    ("The ratio is 1.40%.", {"kind": "number", "value": 1.321, "tolerance": 0.006}, False),
    ("The limit is 1.25%.", {"kind": "number", "value": 1.25, "tolerance": 0, "page": 9}, False),
    ("The limit is 1.25% (page 9).", {"kind": "number", "value": 1.25, "tolerance": 0, "page": 9}, True),
    ("Most arrears are in the north west.", {"kind": "text", "contains": ["North West"]}, True),
])
def test_scorer(answer, expected, ok):
    assert score_answer(answer, expected)[0] is ok


# ---------------------------------------------------------------- export (chapter 14)
def test_excel_pack(tmp_path):
    path = export_monthly_pack(10, tmp_path)
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames == ["Summary", "Triggers", "Arrears by region", "Note"]
    assert wb["Summary"]["A6"].value == "Closing pool balance" and wb["Summary"]["B6"].value == 49151532.52
    assert wb["Triggers"]["A3"].value == "arrears_90_ratio" and wb["Triggers"]["E3"].value == "YES"
    assert wb["Arrears by region"]["A2"].value == "North West"


# ---------------------------------------------------------------- agentic cycle (chapter 15)
def cycle(tmp_path, period, approve, **kw):
    return agentic.run_surveillance(period, memory_dir=tmp_path / "mem", out_dir=tmp_path / "out",
                                    approve=approve, log=lambda m: None, **kw)


def test_approved_note_is_sent(tmp_path):
    r = cycle(tmp_path, 10, True)
    assert r["status"] == "sent" and (tmp_path / "out" / "outbox" / "note_2026_10.md").exists()
    assert r["self_check"]["agree"]


def test_note_without_approval_stays_a_draft(tmp_path):
    r = cycle(tmp_path, 10, False)
    assert r["status"] == "held for approval"
    assert (tmp_path / "out" / "drafts" / "note_2026_10.md").exists()
    assert not (tmp_path / "out" / "outbox").exists()


def test_human_is_asked_when_approval_is_not_given(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)
    assert cycle(tmp_path, 10, None)["status"] == "held for approval"


def test_memory_detects_the_switch_to_sequential(tmp_path):
    cycle(tmp_path, 9, True)
    r = cycle(tmp_path, 10, True)
    assert "Payment mode CHANGED from pro rata to sequential." in r["changes"]
    memory = json.loads((tmp_path / "mem" / "surveillance_memory.json").read_text())
    assert sorted(memory) == ["10", "9"]


def test_incomplete_plan_is_completed_from_the_checklist(tmp_path):
    bad_plan = [{"tool": "run_trigger_tests", "arguments": {"period": 10}, "why": "triggers"}]
    brain = RuleBrain(lambda memory: {"content": json.dumps(bad_plan), "tool_calls": []})
    r = cycle(tmp_path, 10, True, plan_source="model", brain=brain)
    assert len(r["missing_from_plan"]) == 3 and len(r["plan"]) == 4


def test_unreadable_plan_is_replaced_by_the_checklist(tmp_path):
    brain = RuleBrain(lambda memory: {"content": "I will check the triggers first.", "tool_calls": []})
    r = cycle(tmp_path, 10, True, plan_source="model", brain=brain)
    assert len(r["missing_from_plan"]) == 4


def test_failed_self_check_holds_the_note_even_if_approved(tmp_path, monkeypatch):
    monkeypatch.setattr(agentic, "self_check", lambda results, period: {"figure": "x", "trigger_tool": 0.01,
                                                                         "recomputed": 0.02, "agree": False})
    r = cycle(tmp_path, 10, True)
    assert r["status"] == "held" and r["reason"] == "the self-check disagrees"
    assert not (tmp_path / "out" / "outbox").exists()


def test_plan_for_another_period_is_rejected_and_replanned_once(tmp_path):
    wrong = [{"tool": t["tool"], "arguments": {**t.get("arguments", {}), "period": 9}, "why": "x"}
             for t in agentic.CHECKLIST]
    right = agentic.rule_plan(10)
    replies = [json.dumps(wrong), json.dumps(right)]
    calls = []

    def rules(memory):
        calls.append(memory[0]["content"])
        return {"content": replies[len(calls) - 1], "tool_calls": []}
    r = cycle(tmp_path, 10, True, plan_source="model", brain=RuleBrain(rules))
    assert r["replanned"] and len(calls) == 2
    assert "is for period 9, not period 10" in calls[1]
    assert all(s["arguments"]["period"] == 10 for s in r["plan"]) and r["status"] == "sent"


def test_rejected_steps_never_reach_the_note(tmp_path):
    wrong = [{"tool": "run_trigger_tests", "arguments": {"period": 9}, "why": "x"}]
    r = cycle(tmp_path, 10, True, plan_source="model",
              brain=RuleBrain(lambda m: {"content": json.dumps(wrong), "tool_calls": []}))
    assert len(r["rejected_from_plan"]) == 1 and r["replanned"]
    assert "Collection period 10" in r["note"] and r["status"] == "sent"


def test_a_tool_error_holds_the_note_instead_of_crashing(tmp_path, monkeypatch):
    real = agentic.call_tool
    monkeypatch.setattr(agentic, "call_tool", lambda name, args: json.dumps({"error": "data file missing"})
                        if name == "run_trigger_tests" else real(name, args))
    r = cycle(tmp_path, 10, True)
    assert r["status"] == "held" and "missing or failed" in r["reason"]
    assert "run_trigger_tests" in r["note"] and not (tmp_path / "mem" / "surveillance_memory.json").exists()


def test_compare_uses_the_latest_earlier_month(tmp_path):
    cycle(tmp_path, 8, True)
    r = cycle(tmp_path, 10, True)
    assert r["changes"][0].endswith("(0.96% to 1.32%).") and "since period 8" in r["changes"][0]
