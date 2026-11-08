"""The Prospectus Analyser in Dash: upload a prospectus, extract the deal terms, analyse them.

Run from the repository root:

    python python/vol2/ch27/app.py              then open http://127.0.0.1:8050

The layout is built once. Each callback says exactly which inputs it listens to and which
outputs it changes. The work itself is done by the functions in logic.py.
"""

import json
import sys
from pathlib import Path

from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

sys.path.insert(0, str(Path(__file__).resolve().parent))
import logic  # noqa: E402

app = Dash(__name__, title="Prospectus Analyser")
# The server's own limit on a request: the 50 MB file as base64 (4/3 larger) plus the rest of the callback.
app.server.config["MAX_CONTENT_LENGTH"] = logic.MAX_BYTES * 4 // 3 + 1024 * 1024

# ---------------------------------------------------------------- layout: what is on the page

NAVY, GOLD, RED = "#1F2F54", "#B8892B", "#9B2D20"
H6 = {"color": NAVY, "margin": "14px 0 4px 0"}
BUTTON = {"margin": "2px 4px 2px 0"}


def table(id_, columns):
    """A table whose rows the callbacks fill. Ungrounded values, failed checks and breaches show in red."""
    return dash_table.DataTable(
        id=id_, columns=[{"name": c, "id": c} for c in columns], data=[], page_size=15,
        style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "fontSize": 13,
                    "maxWidth": 420},
        style_header={"fontWeight": "bold", "backgroundColor": "#EEF1F6"},
        style_data_conditional=[
            {"if": {"filter_query": '{grounded} = "NOT grounded"'}, "color": RED, "fontWeight": "bold"},
            {"if": {"filter_query": '{result} = "FAIL" || {result} = "BREACH"'}, "color": RED, "fontWeight": "bold"},
        ])


def upload(id_, label, accept):
    return dcc.Upload(id=id_, children=html.Button(label, style=BUTTON), accept=accept, max_size=logic.MAX_BYTES)


sidebar = html.Div(style={"width": "330px", "flex": "none", "padding": "12px", "background": "#F7F8FB",
                          "borderRight": "1px solid #DDE"}, children=[
    html.H6("1. The prospectus", style=H6),
    upload("pdf", "Upload PDF", ".pdf"),
    html.Button("Sample: Thames (auto loans)", id="sample_thames", style=BUTTON),
    html.Button("Sample: Severn (mortgages)", id="sample_severn", style=BUTTON),
    html.Div(id="document"),
    html.H6("2. Extraction", style=H6),
    html.Label("Layer"),
    dcc.RadioItems(id="layer", options=["rules", "model", "both"], value="rules", inline=True),
    html.Label("Model brain"),
    dcc.RadioItems(id="mode", options=["simulated", "replay", "live", "record"], value="simulated", inline=True),
    html.Button("Extract the deal terms", id="extract",
                style={**BUTTON, "background": NAVY, "color": "white", "marginTop": "6px"}),
    html.H6("3. Optional data", style=H6),
    upload("tape", "Loan tape (CSV)", ".csv"),
    upload("report", "Investor report (JSON)", ".json"),
    dcc.Checklist(id="thames_data", options=["Use the Thames sample data"], value=[]),
])

tabs = dcc.Tabs(id="tabs", value="terms", children=[
    dcc.Tab(label="Deal terms", value="terms", children=[
        html.Div(id="status"), html.Div(id="coverage"), html.Div(id="key_score"),
        table("terms_table", ["field", "value", "page", "source", "grounded", "quote"])]),
    dcc.Tab(label="Analysis", value="analysis", children=[
        html.Div(style={"display": "flex", "gap": "12px"}, children=[
            dcc.Graph(id="capital", style={"flex": "5"}),
            html.Div(style={"flex": "7"}, children=[
                html.H6("Credit enhancement", style=H6),
                table("ce", ["class", "balance", "share of notes", "subordination", "reserve support",
                             "credit enhancement", "margin", "rating"]),
                html.H6("Consistency checks", style=H6),
                table("checks", ["check", "result", "detail"])])]),
        html.H6("Triggers", style=H6),
        table("triggers", ["trigger", "measure", "limit", "page", "consequence"]),
        html.H6("Waterfall", style=H6),
        html.Div(id="waterfall")]),
    dcc.Tab(label="Ask", value="ask", children=[
        dcc.Input(id="question", type="text", value="What is the limit of the arrears trigger?",
                  style={"width": "75%", "marginTop": "10px"}),
        dcc.RadioItems(id="ask_mode", options=["rules", "replay", "live"], value="rules", inline=True),
        html.Button("Ask", id="ask", style=BUTTON),
        html.H6("Answer", style=H6), html.Pre(id="answer", style={"whiteSpace": "pre-wrap"}),
        html.H6("Passages used", style=H6), table("passages", ["page", "score", "text"])]),
    dcc.Tab(label="Surveillance", value="surveillance", children=[
        html.P("The trigger tests rerun with the limits read from the prospectus, compared with each report's "
               "own result."),
        html.Div(id="surveillance_status"),
        table("surveillance", ["period", "cumulative default ratio", "default limit", "90+ arrears ratio",
                               "arrears limit", "result", "report says"]),
        html.H6("Uploaded loan tape", style=H6), html.Pre(id="tape_check")]),
    dcc.Tab(label="Export", value="export", children=[
        html.P("Download the extracted terms and the analysis."),
        html.Button("JSON", id="download_json", style=BUTTON),
        html.Button("Excel", id="download_excel", style=BUTTON),
        dcc.Download(id="download")]),
])

app.layout = html.Div(style={"fontFamily": "sans-serif"}, children=[
    html.H3("Prospectus Analyser", style={"background": NAVY, "color": "white", "margin": 0, "padding": "10px 16px",
                                          "borderBottom": f"4px solid {GOLD}"}),
    dcc.Store(id="doc_store"),          # which PDF is loaded: {"path", "name", "sample"}
    dcc.Store(id="terms_store"),        # the extracted terms, as JSON text
    html.Div(style={"display": "flex"}, children=[sidebar, html.Div(tabs, style={"flex": "1", "padding": "8px"})]),
])


# ---------------------------------------------------------------- callbacks: what happens when

@app.callback(Output("doc_store", "data"), Output("document", "children"),
              Input("pdf", "contents"), Input("sample_thames", "n_clicks"), Input("sample_severn", "n_clicks"),
              State("pdf", "filename"), prevent_initial_call=True)
def load_document(contents, _thames, _severn, filename):
    """Step 1: remember which PDF to work on."""
    if ctx.triggered_id == "sample_thames":
        doc = logic.sample_document("thames")
    elif ctx.triggered_id == "sample_severn":
        doc = logic.sample_document("severn")
    else:
        try:
            doc = {"path": logic.decode_upload(contents, filename), "name": filename, "sample": None}
        except ValueError as e:
            return no_update, f"Upload refused: {e}"
    return doc, f"Loaded: {doc['name']}"


@app.callback(Output("terms_store", "data"), Output("status", "children"),
              Output("coverage", "children"), Output("key_score", "children"),
              Input("extract", "n_clicks"), State("doc_store", "data"), State("layer", "value"),
              State("mode", "value"), prevent_initial_call=True)
def extract(_n, doc, layer, mode):
    """Step 2: run the extraction and keep the terms in the store."""
    if not doc:
        return no_update, "Load a prospectus first.", "", ""
    out = logic.run_extraction(doc["path"], layer, mode, doc["sample"])
    if out["terms"] is None:
        return None, out["message"], "", ""
    terms = out["terms"]
    return (json.dumps(terms), f"Extracted with layer '{layer}' ({out['message']}).",
            logic.coverage_text(terms), logic.key_score_text(terms, doc["sample"]))


@app.callback(Output("terms_table", "data"), Output("ce", "data"), Output("capital", "figure"),
              Output("checks", "data"), Output("waterfall", "children"), Output("triggers", "data"),
              Input("terms_store", "data"))
def show_terms(terms_json):
    """Step 3: every time the terms change, redraw the Deal terms and Analysis tabs."""
    if not terms_json:
        return [], [], {}, [], "", []
    terms = json.loads(terms_json)
    result = logic.analysis(terms)
    lists = [html.Div([html.B(title), html.Ol([html.Li(step) for step in steps])])
             for title, steps in logic.waterfall_steps(result).items()]
    figure = logic.capital_structure_figure(result) if result["credit_enhancement"] else {}
    return (logic.terms_rows(terms), logic.ce_rows(result), figure, logic.check_rows(result), lists,
            logic.trigger_rows(terms))


@app.callback(Output("answer", "children"), Output("passages", "data"),
              Input("ask", "n_clicks"), State("question", "value"), State("doc_store", "data"),
              State("ask_mode", "value"), prevent_initial_call=True)
def ask(_n, question, doc, mode):
    """Step 4: the passages with their pages, and an answer."""
    if not doc:
        return "Load a prospectus first.", []
    out = logic.answer_question(doc["path"], question, mode, sample=doc["sample"])
    return out["answer"], [{"page": p["page"], "score": p["score"], "text": p["text"]} for p in out["passages"]]


@app.callback(Output("surveillance_status", "children"), Output("surveillance", "data"),
              Output("tape_check", "children"),
              Input("terms_store", "data"), Input("report", "contents"), Input("tape", "contents"),
              Input("thames_data", "value"))
def surveil(terms_json, report, tape, thames_data):
    """Step 5: test the reported ratios against the limits read from the prospectus."""
    if not terms_json:
        return "Extract the terms first.", [], ""
    try:
        report_path = logic.decode_upload(report, "report.json", kind="json") if report else None
        tape_path = logic.decode_upload(tape, "tape.csv", kind="csv") if tape else None
    except ValueError as e:
        return f"Upload refused: {e}", [], ""
    try:
        out = logic.surveillance(json.loads(terms_json), bool(thames_data), report_path, tape_path)
    finally:                                       # the uploaded copies are read once, then deleted
        for p in (report_path, tape_path):
            if p:
                Path(p).unlink(missing_ok=True)
    status = out["message"] or f"{len(out['rows'])} period(s) tested with the limits extracted from the prospectus."
    tape_text = json.dumps(out["tape"], indent=2) if out["tape"] else "No loan tape uploaded."
    return status, out["rows"], tape_text


@app.callback(Output("download", "data"), Input("download_json", "n_clicks"), Input("download_excel", "n_clicks"),
              State("terms_store", "data"), prevent_initial_call=True)
def export(_json, _xlsx, terms_json):
    """Step 6: send the terms and the analysis to the browser as a file."""
    if not terms_json:
        return no_update
    terms = json.loads(terms_json)
    result = logic.analysis(terms)
    if ctx.triggered_id == "download_excel":
        return dcc.send_bytes(logic.export_excel(terms, result), "deal_terms.xlsx")
    return dict(content=logic.export_json(terms, result), filename="deal_terms.json")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8050
    app.run(debug=False, port=port)
