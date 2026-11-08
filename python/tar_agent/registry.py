"""The tool registry: what the model is told about each tool, and how a call is run.

A model cannot run Python. It can only reply with text such as:

    {"name": "run_trigger_tests", "arguments": {"period": 10}}

The controller (the agent loop) reads that reply, finds the function here, runs
it, and sends the result back to the model as text. The descriptions and
parameter schemas below are what the model reads to decide which tool to call.
The format is the JSON schema used by Ollama, OpenAI and most other providers.
"""

import json

from .tools.loan_tape import validate_loan_tape
from .tools.note import draft_surveillance_note
from .tools.prospectus import search_prospectus
from .tools.stratify import FIELDS, MEASURES, stratify_pool
from .tools.triggers import run_trigger_tests

PERIOD = {"type": "integer", "minimum": 1, "maximum": 12,
          "description": "Collection period: 1 = January 2026, 12 = December 2026."}

TOOLS = {
    "validate_loan_tape": {
        "function": validate_loan_tape,
        "description": "Check the cut-off loan tape received from the originator. Lists every data problem "
                       "(duplicates, missing values, impossible values, wrong names) with a suggested fix, and "
                       "says whether the cleaned tape reconciles with the initial pool balance.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "stratify_pool": {
        "function": stratify_pool,
        "description": "Split the pool into groups and total a measure in each group. Use measure "
                       "'balance_90plus' to find where 90+ day arrears are concentrated.",
        "parameters": {"type": "object", "properties": {
            "by": {"type": "string", "enum": FIELDS, "description": "The field to group by."},
            "period": {"type": "integer", "minimum": 0, "maximum": 12,
                       "description": "0 = cut-off date (31 December 2025); 1-12 = end of that collection period."},
            "measure": {"type": "string", "enum": MEASURES, "description": "What to total in each group."},
        }, "required": ["by"]},
    },
    "run_trigger_tests": {
        "function": run_trigger_tests,
        "description": "Recompute the cumulative default ratio and the 90+ day arrears ratio from the loan-level "
                       "data for one period, compare them with the prospectus limits and with the investor report, "
                       "and say whether principal is paid pro rata or sequentially.",
        "parameters": {"type": "object", "properties": {"period": PERIOD}, "required": ["period"]},
    },
    "search_prospectus": {
        "function": search_prospectus,
        "description": "Search the prospectus and return the most relevant passages with their page numbers. "
                       "Use it for any question about the deal's rules: definitions, limits, fees, priority of "
                       "payments. Answer only from the passages returned and cite the page.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "The question or key words to search for."},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Number of passages (default 3)."},
        }, "required": ["query"]},
    },
    "draft_surveillance_note": {
        "function": draft_surveillance_note,
        "description": "Draft the monthly surveillance note for one period: pool movements, trigger results, "
                       "the main driver of arrears and the note balances. All figures are computed, not estimated.",
        "parameters": {"type": "object", "properties": {"period": PERIOD}, "required": ["period"]},
    },
}


def tool_schemas():
    """The list sent to the model with every request."""
    return [{"type": "function", "function": {"name": name, "description": t["description"],
                                              "parameters": t["parameters"]}}
            for name, t in TOOLS.items()]


def _plain(value):
    """Turn numpy and pandas values into plain Python so they can be written as JSON."""
    if hasattr(value, "item"):
        return value.item()
    return str(value)


def call_tool(name, arguments=None):
    """Run one tool call and return its result as JSON text.

    Errors are returned as text too, never raised: the model reads the error and
    can correct its call on the next step instead of the whole agent stopping.
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"arguments are not valid JSON: {e}"})
    arguments = arguments or {}
    if name not in TOOLS:
        return json.dumps({"error": f"unknown tool '{name}'. Available tools: {sorted(TOOLS)}"})
    allowed = TOOLS[name]["parameters"]["properties"]
    unknown = [k for k in arguments if k not in allowed]
    if unknown:
        return json.dumps({"error": f"unknown argument(s) {unknown} for {name}. Allowed: {sorted(allowed)}"})
    try:
        result = TOOLS[name]["function"](**arguments)
    except (ValueError, TypeError) as e:
        return json.dumps({"error": str(e)})
    return json.dumps(result, default=_plain)


# ---------------------------------------------------------------- Volume 2 Part E: the Prospectus Analyser
# The analyser's tools have their own registry, so the surveillance agent of Parts C and D
# keeps exactly its five tools (and every listing above keeps its line numbers).

from .tools.analyse import analyse_deal_terms as _analyse  # noqa: E402
from .tools.document import search_document  # noqa: E402
from .tools.extract import extract_deal_terms  # noqa: E402

PDF_PATH = {"type": "string", "description": "Path of the prospectus PDF uploaded by the user."}


def _extract_rules(pdf_path):
    return extract_deal_terms(pdf_path, layer="rules")


def _analyse_pdf(pdf_path):
    return _analyse(extract_deal_terms(pdf_path, layer="rules"))


ANALYSER_TOOLS = {
    "extract_deal_terms": {
        "function": _extract_rules,
        "description": "Extract the deal terms of a prospectus PDF with the rules layer: parties, dates, pool "
                       "balance, classes of notes, reserve funds, priority of payments, triggers, eligibility "
                       "criteria and risk retention. Every value has its page, a quote and a grounding flag.",
        "parameters": {"type": "object", "properties": {"pdf_path": PDF_PATH}, "required": ["pdf_path"]},
    },
    "analyse_deal_terms": {
        "function": _analyse_pdf,
        "description": "Credit enhancement of each class, five consistency checks and the priority of payments "
                       "of a prospectus PDF, computed from the extracted terms.",
        "parameters": {"type": "object", "properties": {"pdf_path": PDF_PATH}, "required": ["pdf_path"]},
    },
    "search_document": {
        "function": search_document,
        "description": "Search a prospectus PDF and return the most relevant passages with their page numbers. "
                       "Answer only from the passages returned and cite the page.",
        "parameters": {"type": "object", "properties": {
            "pdf_path": PDF_PATH,
            "query": {"type": "string", "description": "The question or key words to search for."},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Number of passages (default 3)."},
        }, "required": ["pdf_path", "query"]},
    },
}


def analyser_schemas():
    return [{"type": "function", "function": {"name": name, "description": t["description"],
                                              "parameters": t["parameters"]}}
            for name, t in ANALYSER_TOOLS.items()]


def call_analyser_tool(name, arguments=None):
    """The same rules as call_tool, for the analyser's registry."""
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"arguments are not valid JSON: {e}"})
    arguments = arguments or {}
    if name not in ANALYSER_TOOLS:
        return json.dumps({"error": f"unknown tool '{name}'. Available tools: {sorted(ANALYSER_TOOLS)}"})
    allowed = ANALYSER_TOOLS[name]["parameters"]["properties"]
    unknown = [k for k in arguments if k not in allowed]
    if unknown:
        return json.dumps({"error": f"unknown argument(s) {unknown} for {name}. Allowed: {sorted(allowed)}"})
    try:
        result = ANALYSER_TOOLS[name]["function"](**arguments)
    except (ValueError, TypeError) as e:
        return json.dumps({"error": str(e)})
    return json.dumps(result, default=_plain, ensure_ascii=False)
