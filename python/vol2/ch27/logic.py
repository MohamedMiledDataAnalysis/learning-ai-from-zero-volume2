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
import re
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
from tar_agent.data import STANDARD_REGIONS, investor_report, investor_report_path  # noqa: E402
from tar_agent.tools.investor_report import read_investor_report  # noqa: E402
from tar_agent.tools.loan_tape import POOL_CUT, SUPPLEMENTARY, load_clean_tape, validate_loan_tape  # noqa: E402

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

    kind "pdf" accepts a PDF only (a prospectus); kind "csv" a loan tape file (the FCA template file or its
    supplementary file); kind "report" an investor report as a PDF or an Excel workbook (the first bytes tell which).
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
    if kind == "csv" and (raw.startswith(b"PK") or raw.startswith(b"%PDF")):
        raise ValueError(f"{filename} is not a CSV file")
    if kind == "report":
        if raw.startswith(b"%PDF"):
            kind = "pdf"
        elif raw.startswith(b"PK"):
            kind = "xlsx"
        else:
            raise ValueError(f"{filename} is neither a PDF nor an Excel workbook")
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
    """The twelve Thames investor reports, read from Larkmead Bank's PDFs."""
    return [investor_report(period) for period in range(1, 13)]


def surveillance(terms, use_thames_data=False, report_path=None, tape_path=None, supplementary_path=None):
    """The surveillance panel: trigger tests with the extracted limits, plus a tape check if a tape is given."""
    out = {"rows": [], "tape": None, "message": ""}
    reports = []
    try:
        if report_path:
            reports = [read_investor_report(str(report_path))]
        elif use_thames_data:
            reports = thames_reports()
        else:
            out["message"] = ("No investor report: upload one (the cash manager's PDF) or tick "
                              "'Use the Thames sample data'.")
    except (ValueError, StopIteration, OSError) as e:
        out["message"] = f"The investor report could not be read: {e}"
    out["rows"] = surveillance_rows(terms, reports)
    if tape_path or supplementary_path:
        if not tape_path:
            out["tape"] = {"error": "no file starts with the field AUTL1 of the FCA template"}
            return out
        try:
            v = validate_loan_tape(tape_path, supplementary_path)
        except (KeyError, AttributeError, ValueError, OSError) as e:
            out["tape"] = {"error": f"the file is not a loan tape that matches the data dictionary ({e})"}
            return out
        out["tape"] = {"rows received": v["rows_received"], "loans after cleaning": v["loans_after_cleaning"],
                       "issues found": v["issues_found"], "issues by rule": v["issues_by_rule"]}
    return out


# ---------------------------------------------------------------- 6. The deal check: the three files together

# Eligibility criteria the check can test on the tape: a pattern in the criterion's text, and the test.
ELIGIBILITY_TESTS = [
    (r"resident in the United Kingdom", lambda t, n: t.region.isin(STANDARD_REGIONS)),
    (r"hire purchase or personal contract purchase", lambda t, n: t["product"].isin(["HP", "PCP"])),
    (r"days past due equal to 0", lambda t, n: t.days_past_due == 0),
    (r"At least (\d+) instalments had been paid",
     lambda t, n: t.original_term_months - t.remaining_term_months >= n),
    (r"At least (\d+) instalments remained", lambda t, n: t.remaining_term_months >= n),
    (r"loan-to-value was (\d+)% or less", lambda t, n: t.ltv_original_pct <= n),
]


def _row(check, files, page, expected, found, ok):
    return {"check": check, "files": files, "prospectus page": "" if page is None else page,
            "expected": expected, "found": found, "result": "pass" if ok else "FAIL"}


def _missing(check, files):
    return {"check": check, "files": files, "prospectus page": "", "expected": "", "found": "",
            "result": "file not loaded"}


def tape_files(paths):
    """Sort uploaded tape files: the FCA template file starts with the field AUTL1, the supplementary file with
    AUTL2. Returns (template, supplementary); either can be None."""
    template = supplementary = None
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as f:
            first = f.readline()
        if first.startswith("AUTL1,"):
            template = p
        elif first.startswith("AUTL2,"):
            supplementary = p
    return template, supplementary


def deal_check(terms, tape_path=None, report_path=None, supplementary_path=None):
    """Check the prospectus, the loan tape and one investor report against each other, as on a new deal."""
    rows = []
    tape = load_clean_tape(tape_path, supplementary_path) if tape_path else None
    report = read_investor_report(str(report_path)) if report_path else None
    pool = terms["pool_balance"]

    # 1. The tape against the prospectus.
    if tape is None:
        rows.append(_missing("Pool balance at the cut-off date", "tape + prospectus"))
        rows.append(_missing("Eligibility criteria", "tape + prospectus"))
    else:
        total = round(float(tape.current_balance.sum()), 2)
        rows.append(_row("Pool balance at the cut-off date", "tape + prospectus", pool["page"],
                         f"£{pool['value']:,.2f}", f"£{total:,.2f} ({len(tape):,} loans)",
                         pool["value"] is not None and abs(total - pool["value"]) < 0.01))
        for c in terms["eligibility_criteria"]:
            for pattern, test in ELIGIBILITY_TESTS:
                m = re.search(pattern, c["value"] or "")
                if m:
                    n = int(m.group(1)) if m.groups() else None
                    fails = int((~test(tape, n)).sum())
                    rows.append(_row("Eligibility: " + c["value"], "tape + prospectus", c["page"], "every loan",
                                     f"{fails} loan(s) fail", fails == 0))
                    break
            else:
                rows.append({**_row("Eligibility: " + (c["value"] or ""), "tape + prospectus", c["page"], "", "", True),
                             "result": "not tested automatically"})

    # 2. The investor report against the prospectus.
    if report is None:
        for name in ("Notes: balance, margin and rating", "Reserve fund required amount", "Trigger tests"):
            rows.append(_missing(name, "report + prospectus"))
    else:
        reported = {n["class"]: n for n in report["notes"]}
        for c in terms["classes"]:
            name = c["name"]["value"]
            n = reported.get(name)
            found = "not in the report" if n is None else \
                f"£{n['initial_balance']:,.2f}, {n['margin']:.2%}, {n['rating']}"
            ok = n is not None and abs(n["initial_balance"] - c["balance"]["value"]) < 0.01 and \
                abs(n["margin"] - c["margin"]["value"]) < 1e-9 and n["rating"] == c["rating"]["value"]
            rows.append(_row(f"Class {name}: balance, margin and rating", "report + prospectus", c["balance"]["page"],
                             f"£{c['balance']['value']:,.2f}, {c['margin']['value']:.2%}, {c['rating']['value']}",
                             found, ok))
        if terms["reserve_funds"]:
            rf = terms["reserve_funds"][0]["amount"]
            rows.append(_row("Reserve fund required amount", "report + prospectus", rf["page"],
                             f"£{rf['value']:,.2f}", f"£{report['reserve_fund']['required']:,.2f}",
                             abs(report["reserve_fund"]["required"] - rf["value"]) < 0.01))
        for r in surveillance_rows(terms, [report]):
            row = _row(f"Trigger tests, period {r['period']}", "report + prospectus",
                       terms["triggers"][0]["limit"]["page"] if terms["triggers"] else None,
                       f"limits {r['default limit']} and {r['arrears limit']}",
                       f"{r['cumulative default ratio']} and {r['90+ arrears ratio']}", True)
            row["result"] = "pass" if r["result"] == "pass" else "BREACHED"   # a breach is news, not a data error
            rows.append(row)

    # 3. The investor report against the tape: the pool factor is the closing balance over the cut-off balance.
    if tape is None or report is None:
        rows.append(_missing("Pool factor: report closing balance / tape balance", "report + tape"))
    else:
        factor = round(report["pool"]["closing_balance"] / float(tape.current_balance.sum()), 6)
        rows.append(_row("Pool factor: report closing balance / tape balance", "report + tape", None,
                         f"{report['pool']['pool_factor']:.6f} (in the report)", f"{factor:.6f}",
                         abs(factor - report["pool"]["pool_factor"]) < 1e-6))
    return rows


# ---------------------------------------------------------------- 7. Export

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
