"""Tests for Volume 2 Parts A and B (chapters 1 to 6): the figures quoted in the text."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "python" / "vol2"


def load(relpath, name):
    """Import a chapter file under a unique name (other parts have modules with the same file name)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, V2 / relpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(script, *args):
    r = subprocess.run([sys.executable, str(V2 / script), *args], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


# ------------------------------------------------------------ chapter 1
def test_ch01_capital_structure():
    out = run("ch01/deal_figures.py", "notes")
    assert "A        62,964,482.91  85.00%    0.70%     AAA   15.00%  15.00%" in out
    assert "D         2,963,034.49   4.00%    3.50%     BBB    0.00%   0.00%" in out
    assert "not counted in CE: it pays only fees and interest" in out


def test_ch01_spread_equals_period_1_deferred_consideration():
    assert "excess spread £195,396.84, that is 3.17% a year" in run("ch01/deal_figures.py", "spread")
    assert "195,396.84" in run("ch01/deal_figures.py", "waterfall")


def test_ch01_prepayment_and_default_rates():
    pre = run("ch01/deal_figures.py", "prepayments")
    assert "1.51%  16.68%" in pre
    d = run("ch01/deal_figures.py", "defaults")
    assert "Cumulative defaults £640,292.58; recoveries received £98,014.04" in d
    assert "0.298%       3.52%            0.45%" in d


def test_ch01_pool():
    assert "PCP loans: 2,963 (63.03% of the balance)" in run("ch01/deal_figures.py", "pool")


# ------------------------------------------------------------ chapter 2
def test_ch02_inventory_and_story():
    inv = run("ch02/inventory.py")
    assert "5,002 rows x 21 columns" in inv and "54,350 rows x 12 columns" in inv and "9 pages" in inv
    nw = run("ch02/north_west.py")
    assert "    10         9.28%           0.30%            80.0%             11.4%" in nw
    cal = run("ch02/calibration.py")
    assert "    10      1.32%   1.25%                0.45%  sequential" in cal


# ------------------------------------------------------------ chapter 3
def test_ch03_checklist_completes_the_plan():
    out = run("ch03/plan_demo.py", "check")
    assert "Checklist items missing:    2" in out
    assert out.count("(added: missing from the plan)") == 2


def test_ch03_cycle_memory_and_approval():
    out = run("ch03/plan_demo.py", "cycle")
    assert "Note sent: outbox/note_2026_09.md" in out
    assert "Note held for approval: drafts/note_2026_10.md" in out
    assert "Payment mode CHANGED from pro rata to sequential." in out
    assert "Memory file now holds periods: 9, 10" in out


# ------------------------------------------------------------ chapter 4
def test_ch04_injection_scan_and_guards():
    g = load("ch04/guardrails.py", "v2_ch04_guardrails")
    text = json.loads(g.read_servicer_commentary(10))["text"]
    clean, flagged = g.scan_document(text)
    assert len(flagged) == 2 and "ignore your previous instructions" not in clean.lower()
    assert "not permitted" in g.guarded_call("investor_helpdesk", "validate_loan_tape", {})


def test_ch04_naive_blocked_guarded_passes():
    naive = run("ch04/guardrails.py", "naive")
    assert "Answer: All trigger tests passed in period 10." in naive and "BLOCKED" in naive
    guarded = run("ch04/guardrails.py", "guarded")
    assert "1.32% against a limit of 1.25%" in guarded and "Output guardrail: pass" in guarded


def test_ch04_grounding():
    out = run("ch04/guardrails.py", "output")
    assert "1.20% does not appear in any tool result" in out
    assert out.count("-> pass") == 1


# ------------------------------------------------------------ chapter 5
def test_ch05_golden_and_trace():
    assert "Golden file check: identical" in run("ch05/tracing.py", "golden")
    lines = [json.loads(x) for x in run("ch05/tracing.py", "trace").splitlines()]
    assert lines[0]["tool"] == "run_trigger_tests" and lines[-1]["stopped_because"] == "final answer"
    design = run("ch05/tracing.py", "design")
    assert "Questions: 40" in design and "run_trigger_tests          17" in design
    assert "31 numbers, 9 texts; 9 must cite a page" in design


# ------------------------------------------------------------ chapter 6
def test_ch06_mcp_round_trip():
    out = run("ch06/mcp_client.py")
    assert "['run_trigger_tests', 'search_prospectus']" in out
    assert "90+ ratio 1.32%, breached: True, isError: False" in out
    assert '"code": -32602' in out


def test_ch06_mcp_server_unknown_method():
    mcp_server = load("ch06/mcp_server.py", "v2_ch06_mcp_server")
    assert mcp_server.handle({"jsonrpc": "2.0", "id": 9, "method": "initialize", "params": {}})["error"]["code"] \
        in (-32601, -32602)


def test_ch06_pipeline():
    out = run("ch06/multi_agent.py")
    assert "APPROVED: note quotes 1.32%" in out and "REJECTED" in out


@pytest.mark.parametrize("script", [f"ch0{n}/check_ch0{n}.py" for n in range(1, 7)])
def test_checkers_pass_on_the_reference_solution(script):
    assert "PASS" in run(script, "--solution")
