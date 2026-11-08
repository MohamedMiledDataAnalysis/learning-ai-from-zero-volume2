"""Tests for the Dash Prospectus Analyser (Volume 2, chapter 27).

The callbacks are thin: these tests check the logic functions they call, plus a smoke test
that the app builds and its callbacks are registered.
"""

import base64
import io
import json
import shutil
import sys
from pathlib import Path

import pytest
from openpyxl import load_workbook
from pypdf import PdfWriter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "vol2" / "ch27"))

import logic  # noqa: E402
from tar_agent.tools.extract import extract_deal_terms  # noqa: E402
from tar_agent.tools.extract_sim import simulated_model_brain  # noqa: E402

THAMES = str(logic.SAMPLES["thames"]["pdf"])
SEVERN = str(logic.SAMPLES["severn"]["pdf"])
UNUSED = "http://127.0.0.1:9"          # nothing listens on port 9: stands for "Ollama is not running"


def data_url(raw, kind="application/pdf"):
    return f"data:{kind};base64," + base64.b64encode(raw).decode()


@pytest.fixture(scope="module")
def thames_rules():
    return logic.run_extraction(THAMES, "rules", "simulated", "thames")["terms"]


@pytest.fixture(scope="module")
def severn_both():
    return logic.run_extraction(SEVERN, "both", "simulated", "severn")["terms"]


# ---------------------------------------------------------------- extraction and coverage

def test_thames_rules_coverage_and_key(thames_rules):
    assert logic.coverage_text(thames_rules) == "16 of 16 fields found. 0 values failed the page grounding check."
    assert logic.key_score_text(thames_rules, "thames") == "Answer key: 50 of 50 values found, 50 correct."


def test_severn_rules_finds_five_fields():
    terms = logic.run_extraction(SEVERN, "rules", "simulated", "severn")["terms"]
    assert logic.coverage_text(terms).startswith("5 of 16 fields found — missing: currency, pool_balance")
    assert logic.key_score_text(terms, "severn") == "Answer key: 5 of 76 values found, 5 correct."


def test_severn_both_with_simulated_model(severn_both):
    assert severn_both["coverage"]["found"] == 16
    assert logic.key_score_text(severn_both, "severn") == "Answer key: 76 of 76 values found, 76 correct."
    out = logic.run_extraction(SEVERN, "both", "simulated", "severn")
    assert out["message"] == logic.SIMULATED_LABEL


def test_uploaded_document_has_no_answer_key(thames_rules):
    assert logic.key_score_text(thames_rules, None).startswith("No answer key")
    assert logic.run_extraction(THAMES, "model", "simulated", None)["terms"] is None


def test_planted_value_is_shown_as_not_grounded():
    key = json.loads(logic.SAMPLES["severn"]["key"].read_text(encoding="utf-8"))
    terms = extract_deal_terms(SEVERN, layer="model", brain=simulated_model_brain(key, {"classes.B.margin": 0.018}))
    flagged = [r for r in logic.terms_rows(terms) if r["grounded"] == "NOT grounded"]
    assert [(r["field"], r["value"]) for r in flagged] == [("classes[1].margin", "1.80%")]
    assert logic.coverage_text(terms).endswith("1 value failed the page grounding check.")


def test_replay_without_recording_shows_pending_line():
    recording = ROOT / "python" / "recordings" / "vol2-partE-extract-severn.jsonl"
    if recording.exists():
        pytest.skip("a recording exists: replay runs for real")
    assert logic.run_extraction(SEVERN, "model", "replay", "severn")["message"] == logic.PENDING


def test_live_mode_without_ollama_gives_a_message():
    out = logic.run_extraction(SEVERN, "model", "live", "severn", host=UNUSED)
    assert out["terms"] is None and out["message"].startswith("The model could not be reached")
    ans = logic.answer_question(SEVERN, "What is the arrears trigger?", "live", host=UNUSED)
    assert ans["answer"].startswith("The model could not be reached") and ans["passages"]


def test_ask_rules_gives_the_best_passage_with_its_page():
    ans = logic.answer_question(THAMES, "What is the limit of the 90+ day arrears ratio?", "rules")
    assert ans["answer"].startswith("Best passage (page 9, no model used)") and "1.25%" in ans["answer"]
    # Replay never shows the recorded answer for another question or another document.
    assert logic.answer_question(THAMES, "fees", "replay")["answer"].startswith("Replay holds one recorded answer")
    if not logic.ASK_RECORDING.exists():
        q = logic.ASK_RECORDED["question"]
        assert logic.answer_question(SEVERN, q, "replay", sample="severn")["answer"] == logic.PENDING


def test_upload_size_is_checked_before_decoding(monkeypatch):
    monkeypatch.setattr(logic, "MAX_BYTES", 1000)
    big = "data:application/pdf;base64," + "A" * 4000          # 3,000 bytes once decoded
    with pytest.raises(ValueError, match="the limit is"):
        logic.decode_upload(big, "big.pdf")


def test_scanned_pdf_is_explained(tmp_path):
    w = PdfWriter()
    w.add_blank_page(595, 842)
    path = tmp_path / "scan.pdf"
    w.write(path)
    assert logic.run_extraction(str(path), "rules", "simulated")["message"].endswith("needs OCR first)")


# ---------------------------------------------------------------- analysis

def test_credit_enhancement_rows(thames_rules, severn_both):
    t = logic.ce_rows(logic.analysis(thames_rules))
    s = logic.ce_rows(logic.analysis(severn_both))
    assert t[0]["class"] == "A" and t[0]["credit enhancement"] == "15.000%"
    assert s[0]["credit enhancement"] == "13.955%" and s[0]["reserve support"] == "1.455%"
    assert s[-1] == {**s[-1], "class": "Z", "margin": "—", "rating": "Unrated", "credit enhancement": "0.000%"}


def test_checks_and_waterfall(thames_rules, severn_both):
    assert [r["result"] for r in logic.check_rows(logic.analysis(thames_rules))] == ["pass"] * 5
    steps = logic.waterfall_steps(logic.analysis(severn_both))
    assert [len(v) for v in steps.values()] == [17, 7]
    severn_rules = logic.run_extraction(SEVERN, "rules", "simulated", "severn")["terms"]
    assert {r["result"] for r in logic.check_rows(logic.analysis(severn_rules))} == {"not possible"}


def test_capital_structure_figure(severn_both):
    fig = logic.capital_structure_figure(logic.analysis(severn_both))
    assert [t.name for t in fig.data] == ["Class Z", "Class D", "Class C", "Class B", "Class A"]
    assert fig.data[-1].text[0] == "Class A: 87.5% of notes, CE 13.96%"


def test_trigger_rows(thames_rules):
    rows = logic.trigger_rows(thames_rules)
    assert rows[0]["limit"] == "periods 1 to 6: 1.00%; periods 7 to 12: 2.00%"
    assert rows[1]["limit"] == "1.25%" and rows[1]["page"] == 9


# ---------------------------------------------------------------- surveillance

def test_surveillance_with_extracted_limits(thames_rules):
    out = logic.surveillance(thames_rules, True)
    assert len(out["rows"]) == 12
    assert [r["period"] for r in out["rows"] if r["result"] == "BREACH"] == [10, 11, 12]
    assert all((r["result"] == "BREACH") == (r["report says"] == "breached") for r in out["rows"])


def test_surveillance_with_uploaded_report_and_tape(thames_rules, tmp_path):
    report = tmp_path / "report.json"
    shutil.copy(ROOT / "data" / "investor_reports" / "investor_report_2026_10.json", report)
    out = logic.surveillance(thames_rules, False, str(report), str(ROOT / "data" / "loan_tape_cutoff.csv"))
    assert [r["result"] for r in out["rows"]] == ["BREACH"]
    assert out["tape"]["issues found"] == 9


def test_surveillance_without_data_explains(severn_both):
    assert logic.surveillance(severn_both, False)["message"].startswith("No investor report")


# ---------------------------------------------------------------- upload and export

def test_upload_decoding(monkeypatch):
    raw = Path(THAMES).read_bytes()
    path = logic.decode_upload(data_url(raw), "../../etc/passwd.pdf")
    assert Path(path).read_bytes() == raw and Path(path).parent == logic.UPLOAD_DIR
    with pytest.raises(ValueError, match="is not a PDF"):
        logic.decode_upload(data_url(b"hello"), "notes.pdf")
    with pytest.raises(ValueError, match="nothing was uploaded"):
        logic.decode_upload(None, "x.pdf")
    assert logic.size_text(logic.MAX_BYTES) == "50.0 MB"
    monkeypatch.setattr(logic, "MAX_BYTES", 1024)
    with pytest.raises(ValueError, match="the file is 38.1 kB; the limit is 1.0 kB"):
        logic.decode_upload(data_url(raw), "big.pdf")


def test_exports(severn_both):
    result = logic.analysis(severn_both)
    wb = load_workbook(io.BytesIO(logic.export_excel(severn_both, result)))
    assert wb.sheetnames == ["Terms", "Credit enhancement", "Checks"]
    assert wb["Terms"]["A1"].value == "field" and wb["Terms"].max_row == len(logic.terms_rows(severn_both)) + 1
    assert wb["Credit enhancement"]["F2"].value == "13.955%"
    data = json.loads(logic.export_json(severn_both, result))
    assert set(data) == {"terms", "analysis"} and data["analysis"]["checks_passed"] == 5


# ---------------------------------------------------------------- the app itself

def test_app_builds_and_registers_callbacks():
    import app as dash_app
    outputs = " ".join(dash_app.app.callback_map)
    for target in ["doc_store.data", "terms_store.data", "terms_table.data", "answer.children",
                   "surveillance.data", "download.data"]:
        assert target in outputs
    assert len(dash_app.app.callback_map) == 6


def test_extract_callback_end_to_end():
    import app as dash_app
    doc = logic.sample_document("severn")
    terms_json, status, coverage, score = dash_app.extract(1, doc, "both", "simulated")
    assert status.startswith("Extracted with layer 'both'") and coverage.startswith("16 of 16")
    tables = dash_app.show_terms(terms_json)
    assert len(tables[0]) == len(logic.terms_rows(json.loads(terms_json))) and tables[1][0]["class"] == "A"


def test_excel_export_keeps_formula_like_text_as_text(thames_rules):
    import copy
    from tar_agent.tools.analyse import analyse_deal_terms
    terms = copy.deepcopy(thames_rules)
    terms["deal_name"]["quote"] = '=HYPERLINK("http://example.com","Click")'   # a hostile line in an uploaded PDF
    data = logic.export_excel(terms, analyse_deal_terms(terms))
    ws = load_workbook(io.BytesIO(data))["Terms"]
    cells = [c for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    assert cells and all(c.data_type == "s" for c in cells)


# ---------------------------------------------------------------- bad uploads give plain messages, never a crash

def test_csv_that_is_not_a_loan_tape(thames_rules, tmp_path):
    bad = tmp_path / "other.csv"
    bad.write_text("a,b\n1,2\n", encoding="utf-8")
    out = logic.surveillance(thames_rules, tape_path=str(bad))
    assert out["tape"]["error"].startswith("the CSV is not a loan tape")


def test_csv_that_is_not_utf8(thames_rules, tmp_path):
    bad = tmp_path / "latin1.csv"
    bad.write_bytes("loan_id,region\nTAR1,Caf\xe9\n".encode("latin-1"))
    out = logic.surveillance(thames_rules, tape_path=str(bad))
    assert "error" in out["tape"]


def test_damaged_pdf(tmp_path):
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"%PDF-1.5\nthis is not a real PDF")
    assert logic.run_extraction(str(bad), "rules", "simulated")["message"] == "the PDF could not be read (damaged file)"
    assert logic.answer_question(str(bad), "What is the arrears limit?")["answer"] == "the PDF could not be read (damaged file)"


def test_report_that_is_a_list(thames_rules, tmp_path):
    bad = tmp_path / "report.json"
    bad.write_text("[1, 2]", encoding="utf-8")
    out = logic.surveillance(thames_rules, report_path=str(bad))
    assert out["message"].endswith("(expected one JSON object for one period).")
