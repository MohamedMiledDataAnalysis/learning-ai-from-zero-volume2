"""Tests for the shared tools of Volume 2 Part E: reading any PDF, extracting the deal terms,
the grounding check and the analysis. The figures are the ones the Part E chapters quote."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agent_core.brains import RuleBrain
from tar_agent.registry import ANALYSER_TOOLS, TOOLS, call_analyser_tool
from tar_agent.tools.analyse import analyse_deal_terms
from tar_agent.tools.document import normalise_line, read_pages, search_document
from tar_agent.tools.extract import (SECTIONS, coverage, empty_terms, extract_deal_terms, extract_model,
                                     score_against_key)
from tar_agent.tools.extract_sim import simulated_model_brain

ROOT = Path(__file__).resolve().parents[2]
THAMES = ROOT / "data" / "prospectus" / "prospectus.pdf"
SEVERN = ROOT / "data" / "prospectus_rmbs" / "prospectus.pdf"
KEY_T = json.loads((ROOT / "data" / "schemas" / "answers_thames.json").read_text(encoding="utf-8"))
KEY_S = json.loads((ROOT / "data" / "schemas" / "answers_rmbs.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- reading any PDF
def test_normalise_line_joins_split_letters_and_fixes_spaces():
    assert normalise_line("T est 2 — 90+ day  arrears ,  ( pro rata)") == "Test 2 — 90+ day arrears, (pro rata)"
    assert normalise_line("Class B interest") == "Class B interest"        # class letters are never joined


def test_running_header_and_page_numbers_are_removed():
    pages = read_pages(SEVERN)
    assert len(pages) == 122
    assert not any("Offering circular" in ln for p in pages[1:] for ln in p)
    assert not any(ln in ("- 3 -", "-3-") for p in pages for ln in p)


def test_search_any_pdf_finds_the_severn_trigger_page():
    top = search_document(SEVERN, "arrears trigger per cent")["results"][0]
    assert top["page"] == 64 and "2.50 per cent" in top["text"]          # section 8, the Arrears Trigger


# ---------------------------------------------------------------- layer 1: rules
def test_rules_find_every_thames_term():
    t = extract_deal_terms(THAMES, "rules")
    assert t["coverage"] == {"schema_fields": 16, "found": 16, "share": 1.0, "missing": []}
    s = score_against_key(t, KEY_T)
    assert (s["fields"], s["found"], s["correct"]) == (50, 50, 50)
    assert t["ungrounded"] == []


def test_rules_find_only_part_of_severn():
    t = extract_deal_terms(SEVERN, "rules")
    assert t["coverage"]["found"] == 5 and t["coverage"]["share"] == 0.3125
    assert t["coverage"]["missing"] == ["currency", "pool_balance", "parties.servicer", "dates.cut_off",
                                        "dates.closing", "dates.first_payment", "classes", "reserve_funds",
                                        "priority_of_payments", "triggers", "eligibility_criteria"]
    s = score_against_key(t, KEY_S)
    assert (s["fields"], s["found"], s["correct"]) == (76, 5, 5)
    assert t["parties"]["servicer"]["value"] is None                       # "Mortgage Administrator" is not a rule label
    assert t["risk_retention"]["value"] == "randomly selected exposures"


def test_every_rules_value_cites_its_page_and_a_quote():
    t = extract_deal_terms(THAMES, "rules")
    c = t["classes"][1]
    assert c["margin"] == {"value": 0.013, "page": 46, "quote": "Class B £4,444,551.73 6% SONIA + 1.30% AA",
                           "source": "rules", "grounded": True}
    limits = t["triggers"][0]["limit"]["value"]
    assert limits == [{"periods": "1 to 6", "limit": 0.01}, {"periods": "7 to 12", "limit": 0.02}]


# ---------------------------------------------------------------- layer 2: the model (simulated here)
@pytest.mark.parametrize("pdf, key, fields", [(THAMES, KEY_T, 50), (SEVERN, KEY_S, 76)])
def test_simulated_model_fills_the_whole_schema(pdf, key, fields):
    t = extract_deal_terms(pdf, "model", simulated_model_brain(key))
    s = score_against_key(t, key)
    assert t["coverage"]["found"] == 16
    assert (s["found"], s["correct"]) == (fields, fields)
    assert t["ungrounded"] == []
    assert [x["section"] for x in t["model_log"]] == [name for name, _, _ in SECTIONS]


def test_both_layers_keep_rules_values_and_fill_the_gaps():
    t = extract_deal_terms(SEVERN, "both", simulated_model_brain(KEY_S))
    assert t["parties"]["issuer"]["source"] == "rules"
    assert t["parties"]["servicer"]["source"] == "model"
    assert score_against_key(t, KEY_S)["correct"] == 76


def test_grounding_check_catches_a_planted_wrong_value():
    t = extract_deal_terms(SEVERN, "model", simulated_model_brain(KEY_S, plant={"classes.B.margin": 0.018}))
    assert t["ungrounded"] == ["classes[1].margin"]
    assert t["classes"][1]["margin"]["value"] == 0.018 and t["classes"][1]["margin"]["grounded"] is False


def test_grounding_rejects_a_wrong_page():
    t = extract_deal_terms(THAMES, "rules")
    t["pool_balance"]["page"] = 9
    from tar_agent.tools.extract import ground_terms
    assert "pool_balance" in ground_terms(t, THAMES)


def test_invalid_json_is_retried_once():
    replies = iter(['not json', '{"risk_retention": {"value": "vertical slice", "page": 2, "quote": null}}'])
    sim = simulated_model_brain(KEY_T)

    def rules(memory):
        if "SECTION: risk_retention" in memory[1]["content"]:
            return {"content": next(replies), "tool_calls": []}
        return sim.next(memory, [])
    t = extract_model(THAMES, RuleBrain(rules))
    log = {x["section"]: x for x in t["model_log"]}
    assert log["risk_retention"] == {"section": "risk_retention", "attempts": 2, "ok": True}


def test_a_section_that_stays_invalid_is_reported_not_crashed():
    t = extract_model(THAMES, RuleBrain(lambda m: {"content": "{}", "tool_calls": []}))
    assert all(not x["ok"] for x in t["model_log"])
    assert coverage(t)["found"] == 0


def test_model_layer_needs_a_brain():
    with pytest.raises(ValueError, match="needs a brain"):
        extract_deal_terms(THAMES, "model")


# ---------------------------------------------------------------- analysis
def test_thames_credit_enhancement_and_checks():
    a = analyse_deal_terms(extract_deal_terms(THAMES, "rules"))
    ce = {r["class"]: r["credit_enhancement"] for r in a["credit_enhancement"]}
    assert ce == {"A": 0.15, "B": 0.09, "C": 0.04, "D": 0.0}
    assert (a["checks_passed"], a["checks_failed"], a["checks_not_possible"]) == (5, 0, 0)
    assert a["waterfall"]["type"] == "combined" and len(a["waterfall"]["combined"]) == 8


def test_severn_liquidity_reserve_is_not_credit_enhancement():
    a = analyse_deal_terms(extract_deal_terms(SEVERN, "both", simulated_model_brain(KEY_S)))
    rows = {r["class"]: r for r in a["credit_enhancement"]}
    assert rows["A"]["subordination"] == 0.125 and rows["A"]["reserve_support"] == 0.01455
    assert rows["A"]["credit_enhancement"] == 0.13955
    # The General Reserve Fund is sized on Classes A to D and does not cover Class Z.
    assert rows["Z"]["reserve_support"] == 0 and rows["Z"]["credit_enhancement"] == 0
    assert a["checks_passed"] == 5
    assert a["waterfall"]["type"] == "separate"
    assert (len(a["waterfall"]["revenue"]), len(a["waterfall"]["principal"])) == (17, 7)


def test_severn_rules_only_cannot_run_the_checks():
    a = analyse_deal_terms(extract_deal_terms(SEVERN, "rules"))
    assert a["checks_not_possible"] == 5 and a["credit_enhancement"] == []


def test_a_wrong_margin_order_fails_its_check():
    t = extract_deal_terms(THAMES, "rules")
    t["classes"][3]["margin"]["value"] = 0.005
    checks = {c["check"]: c["passed"] for c in analyse_deal_terms(t)["checks"]}
    assert checks["margins rise as seniority falls"] is False


# ---------------------------------------------------------------- registry, answer keys, recordings
def test_surveillance_registry_is_unchanged_and_analyser_has_three_tools():
    assert list(TOOLS) == ["validate_loan_tape", "stratify_pool", "run_trigger_tests", "search_prospectus",
                           "draft_surveillance_note"]
    assert list(ANALYSER_TOOLS) == ["extract_deal_terms", "analyse_deal_terms", "search_document"]
    out = json.loads(call_analyser_tool("analyse_deal_terms", {"pdf_path": str(THAMES)}))
    assert out["checks_passed"] == 5
    assert "no PDF at" in json.loads(call_analyser_tool("extract_deal_terms", {"pdf_path": "missing.pdf"}))["error"]


def test_answer_keys_are_reproduced_by_their_script():
    sys.path.insert(0, str(ROOT / "generator"))
    import build_answer_keys as bk
    assert json.loads(json.dumps(bk.thames_key())) == KEY_T
    assert json.loads(json.dumps(bk.rmbs_key())) == KEY_S


def test_answer_keys_follow_the_schema_shape():
    schema = json.loads((ROOT / "data" / "schemas" / "deal_terms.schema.json").read_text())
    for key in (KEY_T, KEY_S):
        assert set(schema["required"]) <= set(key)
        assert set(empty_terms()) == set(schema["required"])


def test_replay_without_recording_prints_the_pending_line():
    out = subprocess.run([sys.executable, str(ROOT / "python" / "vol2" / "partE" / "record_extraction.py"),
                          "--deal", "severn", "--mode", "replay"], capture_output=True, text=True, cwd=ROOT)
    rec = ROOT / "python" / "recordings" / "vol2-partE-extract-severn.jsonl"
    if not rec.exists():
        assert out.stdout.strip() == "[Recording pending: run python record_all.py with Ollama installed, then rebuild]"
    assert out.returncode == 0


# ---------------------------------------------------------------- answer keys: each quote shows its own value
def test_answer_key_quotes_show_their_values():
    k = json.loads((ROOT / "data" / "schemas" / "answers_thames.json").read_text(encoding="utf-8"))
    assert k["triggers"][0]["limit"]["quote"] == "Periods 1 to 6 1.00%"
    assert k["classes"][1]["share"]["quote"].startswith("Class B ")
    s = json.loads((ROOT / "data" / "schemas" / "answers_rmbs.json").read_text(encoding="utf-8"))
    assert s["classes"][4]["share"]["quote"].startswith("Z 12,000,000")
    assert s["reserve_funds"][1]["percent"]["quote"].startswith("Liquidity Reserve Fund 1.00 per cent")


def test_grounding_needs_the_number_in_its_quote():
    from tar_agent.tools.extract import ground_field
    from tar_agent.tools.document import page_texts
    texts = page_texts(THAMES)
    wrong_quote = {"value": 0.0125, "page": 109, "quote": "Test 3 — Reserve fund. After the previous payment date,",
                   "source": "model", "grounded": None}
    assert ground_field(wrong_quote, texts)["grounded"] is False
    from tar_agent.tools.extract import _value_on_page
    assert not _value_on_page(0.025, "the notes below Class A represent 12.50 per cent")   # not inside 12.50
    assert _value_on_page(0.025, "exceeds 2.50 per cent.")


# ------------------------------------------------------------ a reserve counts by what it can pay, not its name
def _toy_terms(name, can_cover):
    def f(v):
        return {"value": v, "page": 1, "quote": "", "source": "rules", "grounded": True}
    classes = [{"name": f(n), "balance": f(b), "share": f(None), "margin": f(m), "rating": f(None)}
               for n, b, m in [("A", 90.0, 0.01), ("B", 10.0, 0.02)]]
    return {"deal_name": f("Toy"), "pool_balance": f(100.0), "classes": classes,
            "reserve_funds": [{"name": f(name), "amount": f(2.0), "percent": f(0.02), "basis": f(None),
                               "can_cover_losses": f(can_cover)}],
            "priority_of_payments": {"combined": [], "revenue": [], "principal": []}, "triggers": [], "ungrounded": []}


def test_a_liquidity_named_reserve_that_covers_losses_is_counted():
    a = analyse_deal_terms(_toy_terms("Liquidity Reserve Fund", True))
    assert a["credit_enhancement"][0]["credit_enhancement"] == 0.12      # 10% below + 2% reserve
    assert a["reserves"][0]["counted"] is True


def test_a_reserve_fund_that_pays_only_interest_is_not_counted():
    a = analyse_deal_terms(_toy_terms("Reserve Fund", False))
    assert a["credit_enhancement"][0]["credit_enhancement"] == 0.1
    assert a["reserves"][0]["reason"].startswith("not counted: it pays only fees and interest")


def test_a_reserve_whose_purpose_was_not_found_is_not_counted():
    a = analyse_deal_terms(_toy_terms("Reserve Fund", None))
    assert a["credit_enhancement"][0]["credit_enhancement"] == 0.1
    assert a["reserves"][0]["reason"] == "reserve not counted: what it can pay was not found"


def test_reads_cover_on_the_two_prospectuses():
    from tar_agent.tools.extract import reads_cover
    assert reads_cover("The reserve fund is never used to pay principal or deferred consideration.") is False
    assert reads_cover("The General Reserve Fund covers shortfalls of senior expenses and interest on the Class A "
                       "to D Notes, and debit balances on the Class A to D Principal Deficiency Ledgers;") is True
    assert reads_cover("The Liquidity Reserve Fund covers shortfalls of senior expenses and interest on the "
                       "Class A and B Notes only.") is False
