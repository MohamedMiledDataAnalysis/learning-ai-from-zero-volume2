"""Tests for the five tools, run against the deal pack.

Run from the python/ folder:

    python -m pytest -q

The expected figures are the ones printed in the book. If a test fails, the
book and the code disagree, and the book is not built.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from tar_agent.data import DATA_DIR, deal_terms, investor_report
from tar_agent.registry import TOOLS, call_tool, tool_schemas
from tar_agent.tools.loan_tape import load_clean_tape, validate_loan_tape
from tar_agent.tools.note import draft_surveillance_note
from tar_agent.tools.prospectus import search_prospectus
from tar_agent.tools.stratify import FIELDS, stratify_pool
from tar_agent.tools.triggers import first_breach_period, run_trigger_tests

SOLUTIONS = DATA_DIR.parent / "solutions"
PERIODS = range(1, 13)


# ---------------------------------------------------------------- Tool 1
def test_validation_finds_exactly_the_planted_issues():
    result = validate_loan_tape()
    planted = pd.read_csv(SOLUTIONS / "planted_issues.csv", keep_default_na=False)
    assert result["rows_received"] == 5002
    assert result["issues_found"] == 9
    assert {(i["loan_id"], i["column"]) for i in result["issues"]} == set(zip(planted.loan_id, planted.column))


def test_cleaned_tape_reconciles_with_the_initial_pool():
    result = validate_loan_tape()
    assert result["loans_after_cleaning"] == 5000
    assert result["balance_after_cleaning"] == 74075862.24
    assert result["reconciles"]


def test_cleaned_tape_matches_the_solution_except_values_that_cannot_be_known():
    cleaned = load_clean_tape()
    solution = pd.read_csv(SOLUTIONS / "loan_tape_cutoff_clean.csv", keep_default_na=False)
    # The true values of these fields cannot be known from the tape: the tool leaves them missing and flags them.
    assert cleaned.loc[cleaned.loan_id == "TAR02998", "credit_score"].isna().all()
    assert (cleaned.loc[cleaned.loan_id.isin(["TAR00040", "TAR04067"]), "postcode_area"] == "").all()
    cleaned.loc[cleaned.loan_id == "TAR02998", "credit_score"] = 709
    cleaned.loc[cleaned.loan_id == "TAR00040", "postcode_area"] = "NR"
    cleaned.loc[cleaned.loan_id == "TAR04067", "postcode_area"] = "BN"
    pd.testing.assert_frame_equal(cleaned.reset_index(drop=True), solution, check_dtype=False)


# ---------------------------------------------------------------- Tool 2
@pytest.mark.parametrize("by", FIELDS)
def test_cut_off_stratification_adds_up_to_the_pool(by):
    s = stratify_pool(by)
    assert s["total"] == pytest.approx(deal_terms()["initial_pool_balance"], abs=0.01)
    assert sum(r["share_of_total"] for r in s["rows"]) == pytest.approx(1, abs=1e-5)


@pytest.mark.parametrize("period", PERIODS)
def test_period_stratification_matches_the_investor_report(period):
    rep = investor_report(period)
    assert stratify_pool("region", period)["total"] == pytest.approx(rep["pool"]["closing_balance"], abs=0.01)
    assert stratify_pool("product", period, "count")["total"] == rep["pool"]["loans_outstanding"]
    assert stratify_pool("region", period, "balance_90plus")["total"] == pytest.approx(
        rep["arrears"]["3_instalments"]["balance"], abs=0.01)


def test_north_west_drives_the_october_arrears():
    top = stratify_pool("region", 10, "balance_90plus")["rows"][0]
    assert top["group"] == "North West"
    assert top["balance_90plus"] == 519289.63
    assert top["share_of_total"] == pytest.approx(0.7998, abs=1e-4)


def test_missing_credit_score_is_kept_in_a_missing_group():
    rows = {r["group"]: r for r in stratify_pool("credit_score_band")["rows"]}
    assert rows["Missing"]["balance"] > 0


def test_stratify_rejects_bad_arguments():
    with pytest.raises(ValueError):
        stratify_pool("colour")
    with pytest.raises(ValueError):
        stratify_pool("region", 13)


# ---------------------------------------------------------------- Tool 3
@pytest.mark.parametrize("period", PERIODS)
def test_recomputed_triggers_agree_with_every_report(period):
    r = run_trigger_tests(period)
    assert all(t["agrees_with_report"] for t in r["tests"])
    assert r["principal_payment_mode"] == r["report_shows_mode"]


def test_first_breach_is_the_arrears_test_in_october():
    assert first_breach_period() == 10
    oct_ = {t["test"]: t for t in run_trigger_tests(10)["tests"]}
    assert oct_["arrears_90_ratio"]["breached"] and oct_["arrears_90_ratio"]["value"] == 0.01321
    assert not oct_["cumulative_default_ratio"]["breached"]
    assert run_trigger_tests(9)["principal_payment_mode"] == "pro rata"
    assert run_trigger_tests(12)["principal_payment_mode"] == "sequential"


# ---------------------------------------------------------------- Tool 4
@pytest.mark.parametrize("query, page, must_contain", [
    ("What is the limit for the 90+ day arrears ratio?", 109, "1.25%"),     # section 16
    ("servicer fee", 97, "1.00%"),                                          # section 13
    ("margin on Class B notes", 46, "1.30%"),                               # section 4
    ("weighted average interest rate of the pool", 86, "9.31%"),            # section 10
    ("How much is the reserve fund at closing?", 109, "£1,111,137.93"),     # section 16
    ("definition of a defaulted loan", 91, "4 instalments in arrears"),     # section 11
])
def test_search_finds_the_right_page(query, page, must_contain):
    results = search_prospectus(query)["results"]
    assert any(r["page"] == page and must_contain in r["text"] for r in results)


def test_known_limitation_of_keyword_search():
    # BM25 matches exact words: "eligible" does not match "eligibility" in section 11 (page 91).
    # Volume 1, chapter 27 fixes this with stemming and pretrained embeddings. Keep this test so the book's example stays true.
    results = search_prospectus("Which loans were eligible?")["results"]
    assert results[0]["page"] == 76                      # Kestrel's dealer network wins on the word "eligible"
    assert not any("Each loan met the following criteria" in r["text"] for r in results)


# ---------------------------------------------------------------- Tool 5
def test_note_for_the_breach_month():
    note = draft_surveillance_note(10)
    md = note["note_markdown"]
    assert "A trigger event occurred this period" in md
    assert "1.32% against a limit of 1.25% — BREACHED" in md
    assert "North West holds 80.0%" in md
    assert note["key_figures"]["principal_payment_mode"] == "sequential"


@pytest.mark.parametrize("period, headline", [
    (9, "All trigger tests passed"),
    (11, "Principal remains sequential since the trigger event in period 10"),
])
def test_note_headline_follows_the_trigger_history(period, headline):
    assert headline in draft_surveillance_note(period)["note_markdown"]


def test_note_figures_agree_with_the_report():
    for period in PERIODS:
        note = draft_surveillance_note(period)["note_markdown"]
        closing = investor_report(period)["pool"]["closing_balance"]
        assert f"£{closing:,.0f}" in note


# ---------------------------------------------------------------- Registry
def test_every_tool_has_a_schema_and_runs_through_call_tool():
    schemas = tool_schemas()
    assert [s["function"]["name"] for s in schemas] == list(TOOLS)
    examples = {
        "validate_loan_tape": {},
        "stratify_pool": {"by": "region", "period": 10, "measure": "balance_90plus"},
        "run_trigger_tests": {"period": 10},
        "search_prospectus": {"query": "servicer fee"},
        "draft_surveillance_note": {"period": 10},
    }
    for name, args in examples.items():
        result = json.loads(call_tool(name, json.dumps(args)))
        assert "error" not in result, name


@pytest.mark.parametrize("name, args, message", [
    ("run_trigger_test", {"period": 10}, "unknown tool"),
    ("run_trigger_tests", {"month": 10}, "unknown argument"),
    ("run_trigger_tests", {"period": 13}, "period must be"),
    ("run_trigger_tests", "{period: 10}", "not valid JSON"),
])
def test_bad_calls_return_errors_the_model_can_read(name, args, message):
    result = json.loads(call_tool(name, args))
    assert message in result["error"]
