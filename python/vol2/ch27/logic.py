"""The Prospectus Analyser's logic, kept out of the callbacks so it can be tested on its own.

Every function here takes plain Python values and returns plain Python values (or a plotly
figure). app.py only wires them to the screen. The extraction and the analysis themselves
are the shared tools of Part E (tar_agent.tools.extract, analyse, document): the app never
re-implements them.
"""

import base64
import getpass
import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from openpyxl import Workbook  # noqa: E402
from pypdf.errors import PdfReadError  # noqa: E402

from agent_core.brains import OllamaBrain, make_brain  # noqa: E402
from tar_agent.tools.analyse import analyse_deal_terms  # noqa: E402
from tar_agent.tools.document import page_texts, search_document  # noqa: E402
from tar_agent.tools.extract import all_fields, extract_deal_terms, score_against_key  # noqa: E402
from tar_agent.tools.extract_sim import simulated_model_brain  # noqa: E402
from tar_agent.tools.loan_tape import validate_loan_tape  # noqa: E402

MAX_BYTES = 50 * 1024 * 1024                     # the upload limit: 50 MB
PENDING = "[Recording pending: run python record_all.py with Ollama installed, then rebuild]"
SIMULATED_LABEL = "simulated model: answers from the answer key, for teaching (not a language model)"

SAMPLES = {
    "thames": {"label": "Thames Auto Receivables 2026-1 (auto loans)",
               "pdf": ROOT / "data" / "prospectus" / "prospectus.pdf",
               "key": ROOT / "data" / "schemas" / "answers_thames.json"},
    "severn": {"label": "Severn Residential Mortgages 2026-1 (UK mortgages)",
               "pdf": ROOT / "data" / "prospectus_rmbs" / "prospectus.pdf",
               "key": ROOT / "data" / "schemas" / "answers_rmbs.json"},
}
UPLOAD_DIR = Path(tempfile.gettempdir()) / f"prospectus-analyser-{getpass.getuser()}"   # one folder per user
UPLOAD_LIFETIME = 24 * 3600                      # uploads older than a day are deleted
# The Ask tab's recording holds one reply: the pinned model's answer to this question about Severn.
ASK_RECORDING = ROOT / "python" / "recordings" / "vol2-partE-ask.jsonl"
ASK_RECORDED = {"sample": "severn", "question": "What is the limit of the arrears trigger?"}


# ---------------------------------------------------------------- 1. Upload

def size_text(n):
    """A file size for people: '38.1 kB', '50.0 MB'."""
    return f"{n / 1024 / 1024:.1f} MB" if n >= 1024 * 1024 else f"{n / 1024:.1f} kB"


def decode_upload(contents, filename, kind="pdf"):
    """Turn what dcc.Upload sends ("data:<type>;base64,<data>") into a temporary file. Returns its path.

    kind "pdf" accepts a PDF only; kind "csv" a loan tape; kind "json" an investor report.
    """
    if not contents or "," not in contents:
        raise ValueError("nothing was uploaded")
    header, data = contents.split(",", 1)
    if ";base64" not in header:
        raise ValueError("the upload is not base64-encoded")
    size = len(data) * 3 // 4 - data[-2:].count("=")      # the decoded size, known before decoding
    if size > MAX_BYTES:
        raise ValueError(f"the file is {size_text(size)}; the limit is {size_text(MAX_BYTES)}")
    raw = base64.b64decode(data)
    if kind == "pdf" and not raw.startswith(b"%PDF"):
        raise ValueError(f"{filename} is not a PDF (a PDF file starts with %PDF)")
    if kind == "json":
        json.loads(raw.decode("utf-8"))           # raises if the report is not valid JSON
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    for stale in UPLOAD_DIR.iterdir():             # the folder must not grow without limit
        try:
            if time.time() - stale.stat().st_mtime > UPLOAD_LIFETIME:
                stale.unlink(missing_ok=True)
        except FileNotFoundError:                  # another request deleted it first
            pass
    # The user's file name is never used as a path: only the kind chosen by the app gives the extension.
    handle, path = tempfile.mkstemp(suffix="." + kind, dir=UPLOAD_DIR)
    with os.fdopen(handle, "wb") as f:
        f.write(raw)
    return path


def sample_document(name):
    s = SAMPLES[name]
    return {"path": str(s["pdf"]), "name": s["label"], "sample": name}


# ---------------------------------------------------------------- 2. Extract

def extraction_brain(mode, sample=None, host=None):
    """The brain for the model layer. Returns (brain, message); brain is None when it cannot run."""
    if mode == "simulated":
        if sample is None:
            return None, "The simulated model only exists for the two sample prospectuses (it reads their answer keys)."
        key = json.loads(SAMPLES[sample]["key"].read_text(encoding="utf-8"))
        return simulated_model_brain(key), SIMULATED_LABEL
    recording = ROOT / "python" / "recordings" / f"vol2-partE-extract-{sample or 'upload'}.jsonl"
    if mode == "replay":
        if sample is None or not (recording.exists() and recording.stat().st_size):
            return None, PENDING
        return make_brain("replay", recording), f"model, replay of {recording.name}"
    if mode == "live":
        return OllamaBrain(host=host) if host else OllamaBrain(), "model, live (Ollama)"
    if mode == "record":
        return make_brain("record", recording), f"model, recording to {recording.name}"
    raise ValueError("mode must be simulated, replay, live or record")


def run_extraction(pdf_path, layer, mode, sample=None, host=None):
    """Extract the terms. Returns {"terms", "message"} or {"terms": None, "message"} when it cannot run."""
    try:
        if not any(t.strip() for t in page_texts(pdf_path)):
            return {"terms": None, "message": "the PDF has no text (a scanned document needs OCR first)"}
    except PdfReadError:
        return {"terms": None, "message": "the PDF could not be read (damaged file)"}
    brain, message = (None, "rules only") if layer == "rules" else extraction_brain(mode, sample, host)
    if layer != "rules" and brain is None:
        return {"terms": None, "message": message}
    try:
        terms = extract_deal_terms(pdf_path, layer=layer, brain=brain)
    except ValueError as e:                      # e.g. a scanned PDF with no text layer
        return {"terms": None, "message": str(e)}
    except Exception as e:                       # e.g. Ollama not running in live mode
        return {"terms": None, "message": f"The model could not be reached: {type(e).__name__}. "
                                          "Start Ollama, or choose the simulated or replay mode."}
    return {"terms": terms, "message": message}


def show_value(path, value):
    """How a value is printed on screen: money with commas, decimals as percentages, lists as text."""
    if value is None:
        return ""
    last = path.rsplit(".", 1)[-1]
    if isinstance(value, list):
        return "; ".join(f"periods {x['periods']}: {x['limit']:.2%}" if isinstance(x, dict) else str(x) for x in value)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if last in ("margin", "share", "percent") or (last == "limit" and value < 1):
            return f"{value:.2%}"
        if last in ("balance", "amount", "pool_balance") or value >= 1000:
            return f"£{value:,.2f}"
    return str(value)


def terms_rows(terms):
    """One row per extracted value, for the terms table."""
    rows = []
    for path, f in all_fields(terms):
        if f["value"] is None:
            continue
        rows.append({
            "field": path,
            "value": show_value(path, f["value"]),
            "page": f["page"],
            "source": f["source"],
            "grounded": {True: "grounded", False: "NOT grounded", None: ""}[f["grounded"]],
            "quote": f["quote"],
        })
    return rows


def coverage_text(terms):
    c = terms["coverage"]
    text = f"{c['found']} of {c['schema_fields']} fields found"
    if c["missing"]:
        text += " — missing: " + ", ".join(c["missing"])
    n = len(terms["ungrounded"])
    text += f". {n} value{'s' if n != 1 else ''} failed the page grounding check."
    return text


def key_score_text(terms, sample):
    """Only for the two samples, which have answer keys."""
    if sample is None:
        return "No answer key for an uploaded prospectus: check the values against the quotes."
    key = json.loads(SAMPLES[sample]["key"].read_text(encoding="utf-8"))
    s = score_against_key(terms, key)
    return f"Answer key: {s['found']} of {s['fields']} values found, {s['correct']} correct."


# ---------------------------------------------------------------- 3. Analyse

def analysis(terms):
    return analyse_deal_terms(terms)


def _fmt(x, pattern):
    """Format a number, or show a dash when the prospectus gives none (Class Z has no margin or rating)."""
    return "—" if x is None else format(x, pattern)


def ce_rows(result):
    return [{"class": r["class"], "balance": "£" + _fmt(r["balance"], ",.2f"),
             "share of notes": _fmt(r["share_of_notes"], ".2%"), "subordination": _fmt(r["subordination"], ".2%"),
             "reserve support": _fmt(r["reserve_support"], ".3%"),
             "credit enhancement": _fmt(r["credit_enhancement"], ".3%"), "margin": _fmt(r["margin"], ".2%"),
             "rating": r["rating"] or "unrated"} for r in result["credit_enhancement"]]


def check_rows(result):
    status = {True: "pass", False: "FAIL", None: "not possible"}
    return [{"check": c["check"], "result": status[c["passed"]], "detail": c["detail"]} for c in result["checks"]]


def capital_structure_figure(result):
    """A stacked bar of the notes: the most junior class at the bottom, each segment labelled with its CE."""
    fig = go.Figure()
    rows = list(reversed(result["credit_enhancement"]))      # junior first, so Class A sits on top
    for r in rows:
        fig.add_trace(go.Bar(
            x=["Notes"], y=[r["share_of_notes"] * 100], name=f"Class {r['class']}",
            text=[f"Class {r['class']}: {r['share_of_notes']:.1%} of notes, CE {r['credit_enhancement']:.2%}"],
            textposition="inside", insidetextanchor="middle"))
    fig.update_layout(barmode="stack", height=420, width=520, showlegend=False,
                      yaxis_title="% of the notes", margin={"l": 60, "r": 20, "t": 40, "b": 30},
                      title="Capital structure and credit enhancement (CE)", template="simple_white",
                      uniformtext_minsize=10, uniformtext_mode="hide")   # hide labels too small to read
    return fig


def waterfall_steps(result):
    """The priority of payments as numbered lists: one combined list, or revenue and principal."""
    w = result["waterfall"]
    if w["type"] == "combined":
        return {"Combined priority of payments": w["combined"]}
    return {"Revenue priority of payments": w["revenue"], "Principal priority of payments": w["principal"]}


def trigger_rows(terms):
    return [{"trigger": t["name"]["value"], "measure": t["measure"]["value"],
             "limit": show_value("triggers.limit", t["limit"]["value"]), "page": t["limit"]["page"],
             "consequence": t["consequence"]["value"]} for t in terms["triggers"]]


# ---------------------------------------------------------------- 4. Ask

def answer_question(pdf_path, question, mode="rules", host=None, top_k=3, recording=None, sample=None):
    """Passages with their pages, and an answer.

    rules  the best passage itself, no model used
    replay the recorded reply of the model, only for the recorded question about the recorded sample
           (pending line if there is no recording yet)
    live   a local model answers from the passages only and cites the page
    record as live, and saves the reply for replay
    """
    if not question or not question.strip():
        return {"passages": [], "answer": "Type a question first."}
    try:
        passages = search_document(pdf_path, question, top_k=top_k)["results"]
    except ValueError as e:
        return {"passages": [], "answer": str(e)}
    except PdfReadError:
        return {"passages": [], "answer": "the PDF could not be read (damaged file)"}
    if not passages:
        return {"passages": [], "answer": "No passage of the document matches the question."}
    if mode == "rules":
        top = passages[0]
        return {"passages": passages, "answer": f"Best passage (page {top['page']}, no model used): {top['text']}"}
    if mode == "replay" and recording is None:
        # A recording replays the answer to the question it was made with: never show it for another one.
        if sample != ASK_RECORDED["sample"] or question.strip() != ASK_RECORDED["question"]:
            return {"passages": passages,
                    "answer": f"Replay holds one recorded answer: the {ASK_RECORDED['sample'].title()} sample, "
                              f"question \"{ASK_RECORDED['question']}\". Choose rules, or live with Ollama."}
    recording = recording or ASK_RECORDING
    if mode == "replay" and not (Path(recording).exists() and Path(recording).stat().st_size):
        return {"passages": passages, "answer": PENDING}
    context = "\n\n".join(f"[page {p['page']}] {p['text']}" for p in passages)
    memory = [{"role": "system", "content": "You answer questions about a securitisation prospectus. "
                                            "Use only the passages given. Cite the page as (page N). "
                                            "If the passages do not answer, say so."},
              {"role": "user", "content": f"Passages:\n{context}\n\nQuestion: {question}"}]
    try:
        if mode in ("replay", "record"):
            brain = make_brain(mode, recording)
        else:
            brain = OllamaBrain(host=host) if host else OllamaBrain()
        reply = brain.next(memory, [])
    except Exception as e:
        return {"passages": passages, "answer": f"The model could not be reached: {type(e).__name__}."}
    return {"passages": passages, "answer": reply["content"]}


# ---------------------------------------------------------------- 5. Surveillance with the extracted limits

def extracted_limits(terms):
    """The two Thames-style limits from the extracted triggers: cumulative default schedule and 90+ arrears."""
    out = {"cumulative_default": None, "arrears_90": None}
    for t in terms["triggers"]:
        measure = (t["measure"]["value"] or "").lower()
        if "cumulative default" in measure:
            out["cumulative_default"] = t["limit"]["value"]
        elif "90+" in measure or "arrears" in measure:
            out["arrears_90"] = t["limit"]["value"]
    return out


def _limit_for(schedule, period):
    if isinstance(schedule, (int, float)):
        return schedule
    for step in schedule or []:
        first, last = (int(x) for x in step["periods"].split(" to "))
        if first <= period <= last:
            return step["limit"]
    return None


def surveillance_rows(terms, reports):
    """Compare the reported ratios of each investor report with the limits extracted from the prospectus."""
    limits = extracted_limits(terms)
    rows = []
    for rep in reports:
        p = rep["period"]
        cdr = rep["triggers"]["cumulative_default_ratio"]["value"]
        a90 = rep["triggers"]["arrears_90_ratio"]["value"]
        cdr_lim = _limit_for(limits["cumulative_default"], p)
        a90_lim = limits["arrears_90"]
        breach = (cdr_lim is not None and cdr > cdr_lim) or (a90_lim is not None and a90 > a90_lim)
        rows.append({"period": p, "cumulative default ratio": f"{cdr:.2%}",
                     "default limit": "" if cdr_lim is None else f"{cdr_lim:.2%}",
                     "90+ arrears ratio": f"{a90:.2%}", "arrears limit": "" if a90_lim is None else f"{a90_lim:.2%}",
                     "result": "BREACH" if breach else "pass",
                     "report says": "breached" if (rep["triggers"]["cumulative_default_ratio"]["breached"]
                                                   or rep["triggers"]["arrears_90_ratio"]["breached"]) else "pass"})
    return rows


def thames_reports():
    folder = ROOT / "data" / "investor_reports"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("investor_report_*.json"))]


def surveillance(terms, use_thames_data=False, report_path=None, tape_path=None):
    """The surveillance panel: trigger tests with the extracted limits, plus a tape check if a tape is given."""
    out = {"rows": [], "tape": None, "message": ""}
    if report_path:
        reports = [json.loads(Path(report_path).read_text(encoding="utf-8"))]
    elif use_thames_data:
        reports = thames_reports()
    else:
        reports = []
        out["message"] = ("No investor report: upload one (JSON, in the book's format) or tick "
                          "'Use the Thames sample data'.")
    try:
        out["rows"] = surveillance_rows(terms, reports)
    except KeyError as e:
        out["message"] = f"The investor report is not in the book's format (missing {e})."
    except TypeError:
        out["message"] = "The investor report is not in the book's format (expected one JSON object for one period)."
    if tape_path:
        try:
            v = validate_loan_tape(tape_path)
        except (KeyError, AttributeError, ValueError, pd.errors.ParserError) as e:   # UnicodeDecodeError is a ValueError
            out["tape"] = {"error": f"the CSV is not a loan tape in the book's format ({type(e).__name__})"}
            return out
        out["tape"] = {"rows received": v["rows_received"], "loans after cleaning": v["loans_after_cleaning"],
                       "issues found": v["issues_found"], "issues by rule": v["issues_by_rule"]}
    return out


# ---------------------------------------------------------------- 6. Export

def export_json(terms, result):
    return json.dumps({"terms": terms, "analysis": result}, indent=2, ensure_ascii=False, default=str)


def export_excel(terms, result):
    """Three sheets: Terms (every value with page and grounding), Credit enhancement, Checks."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Terms"
    ws.append(["field", "value", "page", "source", "grounded", "quote"])
    for r in terms_rows(terms):
        ws.append([r["field"], r["value"], r["page"], r["source"], r["grounded"], r["quote"]])
    ws2 = wb.create_sheet("Credit enhancement")
    rows = ce_rows(result)
    if rows:
        ws2.append(list(rows[0]))
        for r in rows:
            ws2.append(list(r.values()))
    ws3 = wb.create_sheet("Checks")
    ws3.append(["check", "result", "detail"])
    for r in check_rows(result):
        ws3.append(list(r.values()))
    # Text from an uploaded PDF must stay text: openpyxl would turn "=..." into a live Excel formula.
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value[:1] in ("=", "+", "-", "@"):
                    cell.data_type = "s"
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
