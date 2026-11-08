"""Chapter 28: two guardrails against agent-specific risks.

grounding_check   every number in an answer must appear in the question or in a tool result
                  (a defence against invented figures, also called hallucinated figures)
scan_for_instructions   flag text inside documents that gives orders to an AI
                  (a defence against prompt injection)
"""

import json
import re

NUMBER = re.compile(r"£?\d[\d,]*(?:\.\d+)?%?")
INSTRUCTION_PATTERNS = [
    r"ignore (all |any |your )?(previous |prior |earlier )?instructions",
    r"disregard (the |your )?(system |previous )?(prompt|instructions)",
    r"\byou are now\b",
    r"\b(note|message) to (any |the )?(ai|assistant|model|agent)\b",
    r"\bdo not (tell|mention|report)\b",
    r"\b(state|say|report) that all\b",
]


def numbers_in(text):
    """Every number written in a text, as (written form, value). 1.32% gives value 0.0132."""
    found = []
    for raw in NUMBER.findall(text):
        clean = raw.replace("£", "").replace(",", "")
        value = float(clean.rstrip("%"))
        found.append((raw, value / 100 if raw.endswith("%") else value))
    return found


def _all_values(obj, out):
    """Collect every number in a tool result: JSON values and numbers written inside strings."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        out.extend(v for _, v in numbers_in(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _all_values(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _all_values(v, out)


def grounding_check(answer, question, tool_results):
    """Return the numbers in the answer that cannot be traced to the question or a tool result."""
    known = [v for _, v in numbers_in(question)]
    for result in tool_results:
        _all_values(json.loads(result) if isinstance(result, str) else result, known)
    ungrounded = []
    for raw, value in numbers_in(answer):
        # A percentage printed with 2 decimals is within 0.005 percentage points of the exact value;
        # an amount printed to the penny is within £0.005.
        tolerance = 0.00005 if raw.endswith("%") else 0.005
        if not any(abs(value - k) <= tolerance for k in known):
            ungrounded.append(raw)
    return ungrounded


def scan_for_instructions(text):
    """Return the lines of a document that look like orders addressed to an AI."""
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        if any(re.search(p, line, flags=re.I) for p in INSTRUCTION_PATTERNS):
            hits.append((number, line.strip()))
    return hits
