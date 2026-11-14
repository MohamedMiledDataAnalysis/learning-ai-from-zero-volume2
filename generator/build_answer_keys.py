"""Build the deal-terms JSON schema and the answer keys of the two prospectuses.

Run from the repository root, after both prospectuses are built:

    python generator/build_answer_keys.py

Writes data/schemas/deal_terms.schema.json, answers_thames.json and answers_rmbs.json.
Every expected value comes from a terms file (generator/deal_terms.py through
data/deal_terms.json, and generator/rmbs_terms.py) or, for the Thames lists written
only in the prospectus text, from data/prospectus/prospectus.md. Nothing is typed.
The page and the quote of each value are found by reading the PDF.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "generator"))

import rmbs_terms as R  # noqa: E402
from tar_agent.tools.document import page_texts, read_pages  # noqa: E402
from tar_agent.tools.extract import _candidates, _cover_field, _value_on_page, alnum, empty_terms, field  # noqa: E402

OUT = ROOT / "data" / "schemas"
THAMES_PDF = ROOT / "data" / "prospectus" / "prospectus.pdf"
RMBS_PDF = ROOT / "data" / "prospectus_rmbs" / "prospectus.pdf"


def quote_line(value, lines, key=""):
    """The first line that shows the value itself.

    A number must be written there as a whole number ("6%" is not read inside "62,964,482.91"); a step
    schedule is quoted by the line of its first step ("Periods 1 to 6 1.00%"), never by another sentence
    that happens to contain a "1".
    """
    if isinstance(value, list) and value and isinstance(value[0], dict):
        first = value[0]
        return next((ln for ln in lines if alnum(first["periods"]) in alnum(ln)
                     and _value_on_page(first["limit"], ln)), None)
    if isinstance(value, (int, float)) and not isinstance(value, bool) or \
            (isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)):
        return next((ln for ln in lines if _value_on_page(value, ln, key)), None)
    first = value[0] if isinstance(value, list) else value
    needles = [alnum(c) for c in _candidates(first)]
    return next((ln for ln in lines if any(n and n in alnum(ln) for n in needles)), None)


def locate(value, pdf, key="", hint=None, anchor=None):
    """The page where the value is written, and the line that shows it.

    anchor (a class row such as "B 16,000,000", a reserve or trigger name) makes the search for the line start
    at the first line that contains it, so Class Z's 3.00% is quoted from the Class Z row, not the Class C row.
    """
    texts, pages = page_texts(pdf), read_pages(pdf)
    order = list(range(len(texts)))
    if hint:                       # the section's first page, then the pages after it, then the earlier pages
        order = order[hint - 1:] + order[:hint - 1]
    for i in order:
        if value is not None and _value_on_page(value, texts[i], key):
            lines = pages[i]
            start = next((j for j, ln in enumerate(lines) if anchor and alnum(anchor) in alnum(ln)), 0)
            line = quote_line(value, lines[start:], key) or quote_line(value, lines, key)
            return field(value, i + 1, line, "answer key")
    return field(value, None, None, "answer key")


def keyed(value, pdf, key="", hint=None, anchor=None):
    f = locate(value, pdf, key, hint, anchor)
    f["grounded"] = f["page"] is not None
    return f


def cover_keyed(value, name, pdf):
    """What a reserve fund can pay: the truth comes from the terms file, the page and quote from the PDF.

    The sentence found must say the same thing as the terms file, or the build stops.
    """
    f = _cover_field(name, page_texts(pdf))
    if f["value"] is not value:
        raise SystemExit(f"{name}: the prospectus says can_cover_losses={f['value']}, the terms file says {value}")
    f["source"], f["grounded"] = "answer key", True
    return f


def section_page(pdf, heading):
    """The page on which a section starts: the first page with a line that is exactly the heading (the contents
    page writes the heading followed by dots and a page number, so it never matches)."""
    for i, lines in enumerate(read_pages(pdf)):
        if heading in lines:
            return i + 1
    raise SystemExit(f"{pdf.name}: no page starts the section {heading!r}")


def row(name, balance):
    """The anchor of a class row: its name followed by its balance, as the notes table writes it."""
    return f"{name} {balance:,.2f}" if balance != int(balance) else f"{name} {balance:,.0f}"


def thames_key():
    t = json.loads((ROOT / "data" / "deal_terms.json").read_text(encoding="utf-8"))
    md = (ROOT / "data" / "prospectus" / "prospectus.md").read_text(encoding="utf-8")
    pdf, d = THAMES_PDF, t["deal"]
    S = lambda heading: section_page(pdf, heading)  # noqa: E731
    k = empty_terms()
    k["deal_name"] = keyed(d["issuer"], pdf, hint=1)
    k["currency"] = keyed(d["currency"], pdf, "currency", hint=S("1. Transaction overview"))
    k["pool_balance"] = keyed(t["initial_pool_balance"], pdf, hint=S("1. Transaction overview"))
    k["parties"] = {"issuer": keyed(d["issuer"], pdf, hint=S("1. Transaction overview")), "originator": keyed(d["originator"], pdf, hint=S("1. Transaction overview")),
                    "servicer": keyed(d["servicer"], pdf, hint=S("1. Transaction overview")), "trustee": keyed(d["trustee"], pdf, hint=S("1. Transaction overview"))}
    k["dates"] = {"cut_off": keyed(d["cut_off_date"], pdf, hint=S("1. Transaction overview")), "closing": keyed(d["closing_date"], pdf, hint=S("1. Transaction overview")),
                  "first_payment": keyed(d["first_payment_date"], pdf, hint=S("1. Transaction overview"))}
    total = sum(t["initial_note_balances"].values())
    anchors = {c["name"]: row(c["name"], t["initial_note_balances"][c["name"]]) for c in t["classes"]}
    k["classes"] = [{"name": keyed(c["name"], pdf, hint=S("4. The notes"), anchor=anchors[c["name"]]),
                     "balance": keyed(t["initial_note_balances"][c["name"]], pdf, hint=S("4. The notes"), anchor=anchors[c["name"]]),
                     "share": keyed(c["share"], pdf, hint=S("4. The notes"), anchor=anchors[c["name"]]),
                     "margin": keyed(c["margin"], pdf, hint=S("4. The notes"), anchor=anchors[c["name"]]),
                     "rating": keyed(c["rating"], pdf, hint=S("4. The notes"), anchor=anchors[c["name"]])} for c in t["classes"]]
    pct = t["reserve_fund"]["required_pct_of_initial_notes"]
    k["reserve_funds"] = [{"name": keyed("Reserve fund", pdf, hint=S("16. Reserve fund and trigger events")),
                           "amount": keyed(t["reserve_fund_required_amount"], pdf, hint=S("16. Reserve fund and trigger events"), anchor="Reserve fund."),
                           "percent": keyed(pct, pdf, hint=S("16. Reserve fund and trigger events"), anchor="Reserve fund."),
                           "basis": keyed(["A", "B", "C", "D"], pdf, hint=S("4. The notes")),
                           "can_cover_losses": cover_keyed(t["reserve_fund"]["can_cover_losses"], "Reserve fund", pdf)}]
    section5 = re.split(r"# \d+\. Priority of payments", md)[1].split("\n# ")[0]
    labels = [re.sub(r"\.$", "", m) for m in re.findall(r"^\d+\. \*\*(.+?)\*\*", section5, flags=re.M)]
    k["priority_of_payments"]["combined"] = [keyed(x, pdf, hint=S("15. Priority of payments")) for x in labels]
    sched = [{"periods": f"{a} to {b}", "limit": lim} for a, b, lim in t["triggers"]["cum_default_schedule"]]
    k["triggers"] = [
        {"name": keyed("Cumulative default ratio", pdf, hint=S("16. Reserve fund and trigger events")), "measure": keyed("cumulative default ratio", pdf, hint=S("16. Reserve fund and trigger events")),
         "limit": keyed(sched, pdf, hint=S("16. Reserve fund and trigger events"), anchor="Cumulative default ratio"),
         "consequence": keyed("sequentially", pdf, hint=S("16. Reserve fund and trigger events"))},
        {"name": keyed("90+ day arrears ratio", pdf, hint=S("16. Reserve fund and trigger events")), "measure": keyed("90+ day arrears ratio", pdf, hint=S("16. Reserve fund and trigger events")),
         "limit": keyed(t["triggers"]["arrears_90_limit"], pdf, hint=S("16. Reserve fund and trigger events"), anchor="90+ day arrears ratio"),
         "consequence": keyed("sequentially", pdf, hint=S("16. Reserve fund and trigger events"))},
        {"name": keyed("Reserve fund", pdf, hint=S("16. Reserve fund and trigger events")), "measure": keyed("reserve fund", pdf, hint=S("16. Reserve fund and trigger events")),
         "limit": keyed("required amount", pdf, hint=S("16. Reserve fund and trigger events")), "consequence": keyed("sequentially", pdf, hint=S("16. Reserve fund and trigger events"))},
    ]
    criteria = md.split("met the following criteria at the cut-off date:")[1].split("\n\n")[1]
    k["eligibility_criteria"] = [keyed(re.sub(r"^\d+\. ", "", ln), pdf, hint=S("11. Eligibility criteria and definitions")) for ln in criteria.splitlines()]
    method = re.search(r"holds it as a \*(.+?)\*", md).group(1)
    k["risk_retention"] = keyed(method, pdf, hint=S("1. Transaction overview"))
    return k


def rmbs_key():
    pdf, d = RMBS_PDF, R.DEAL
    S = lambda heading: section_page(pdf, heading)  # noqa: E731
    k = empty_terms()
    k["deal_name"] = keyed(d["issuer"], pdf, hint=1)
    k["currency"] = keyed(d["currency"], pdf, "currency", hint=S("Key Terms"))
    k["pool_balance"] = keyed(d["pool_balance"], pdf, hint=S("Key Terms"))
    k["parties"] = {"issuer": keyed(d["issuer"], pdf, hint=S("Key Terms")), "originator": keyed(d["seller"], pdf, hint=S("Key Terms")),
                    "servicer": keyed(d["mortgage_administrator"], pdf, hint=S("Key Terms")), "trustee": keyed(d["trustee"], pdf, hint=S("Key Terms"))}
    k["dates"] = {"cut_off": keyed(d["portfolio_reference_date"], pdf, hint=S("Key Terms")),
                  "closing": keyed(d["issue_date"], pdf, hint=S("Key Terms")),
                  "first_payment": keyed(d["first_interest_payment_date"], pdf, hint=S("Key Terms"))}
    total = sum(c["balance"] for c in R.CLASSES)
    k["classes"] = [{"name": keyed(c["name"], pdf, hint=S("Section 3 — The Notes"), anchor=row(c["name"], c["balance"])),
                     "balance": keyed(c["balance"], pdf, hint=S("Section 3 — The Notes"), anchor=row(c["name"], c["balance"])),
                     "share": keyed(round(c["balance"] / total, 6), pdf, hint=S("Section 3 — The Notes"), anchor=row(c["name"], c["balance"])),
                     "margin": keyed(c["margin"], pdf, hint=S("Section 3 — The Notes"), anchor=row(c["name"], c["balance"]))
                     if c["margin"] is not None else field(None),
                     "rating": keyed(c["rating"], pdf, hint=S("Section 3 — The Notes"), anchor=row(c["name"], c["balance"]))} for c in R.CLASSES]
    k["reserve_funds"] = []
    for r in R.RESERVES:
        amount = round(r["percent"] * sum(c["balance"] for c in R.CLASSES if c["name"] in r["basis"]), 2)
        k["reserve_funds"].append({"name": keyed(r["name"], pdf, hint=S("Section 5 — Credit Structure")),
                                   "amount": keyed(amount, pdf, hint=S("Section 5 — Credit Structure"), anchor=r["name"]),
                                   "percent": keyed(r["percent"], pdf, hint=S("Section 5 — Credit Structure"), anchor=r["name"]),
                                   "basis": keyed(r["basis"], pdf, hint=S("Section 5 — Credit Structure")),
                                   "can_cover_losses": cover_keyed(r["can_cover_losses"], r["name"], pdf)})
    k["priority_of_payments"]["revenue"] = [keyed(x, pdf, hint=S("Section 6 — Revenue Priority of Payments")) for x in R.REVENUE_PRIORITY]
    k["priority_of_payments"]["principal"] = [keyed(x, pdf, hint=S("Section 7 — Principal Priority of Payments")) for x in R.PRINCIPAL_PRIORITY]
    k["triggers"] = [{"name": keyed(t["name"], pdf, hint=S("Section 8 — Trigger Events")), "measure": keyed(t["measure"], pdf, hint=S("Section 8 — Trigger Events")),
                      "limit": keyed(t["limit"], pdf, hint=S("Section 8 — Trigger Events"), anchor=t["name"]), "consequence": keyed("Sequential Payment Trigger", pdf, hint=S("Section 8 — Trigger Events"))}
                     for t in R.TRIGGERS]
    k["eligibility_criteria"] = [keyed(w.rstrip("."), pdf, hint=S("Section 12 — Lending Criteria and Loan Warranties")) for w in R.LOAN_WARRANTIES]
    k["risk_retention"] = keyed(R.RISK_RETENTION_METHOD, pdf, hint=S("Section 17 — Risk Retention and Regulatory Disclosures"))
    k["definitions"] = {term: keyed(text, pdf, hint=S("Glossary of Defined Terms")) for term, text in R.DEFINITIONS.items()}
    return k


FIELD_SCHEMA = {"type": "object", "required": ["value", "page", "quote", "source", "grounded"], "properties": {
    "value": {}, "page": {"type": ["integer", "null"]}, "quote": {"type": ["string", "null"]},
    "source": {"enum": ["rules", "model", "answer key", None]}, "grounded": {"type": ["boolean", "null"]}}}
F = {"$ref": "#/$defs/field"}
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Deal terms extracted from a securitisation prospectus",
    "$defs": {"field": FIELD_SCHEMA},
    "type": "object",
    "required": ["deal_name", "currency", "pool_balance", "parties", "dates", "classes", "reserve_funds",
                 "priority_of_payments", "triggers", "eligibility_criteria", "risk_retention", "definitions"],
    "properties": {
        "deal_name": F, "currency": F, "pool_balance": F,
        "parties": {"type": "object", "properties": {k: F for k in ("issuer", "originator", "servicer", "trustee")}},
        "dates": {"type": "object", "properties": {k: F for k in ("cut_off", "closing", "first_payment")}},
        "classes": {"type": "array", "items": {"type": "object", "properties": {
            k: F for k in ("name", "balance", "share", "margin", "rating")}}},
        "reserve_funds": {"type": "array", "items": {"type": "object", "properties": {
            k: F for k in ("name", "amount", "percent", "basis", "can_cover_losses")}}},
        "priority_of_payments": {"type": "object", "properties": {
            k: {"type": "array", "items": F} for k in ("combined", "revenue", "principal")}},
        "triggers": {"type": "array", "items": {"type": "object", "properties": {
            k: F for k in ("name", "measure", "limit", "consequence")}}},
        "eligibility_criteria": {"type": "array", "items": F},
        "risk_retention": F,
        "definitions": {"type": "object", "additionalProperties": F},
    },
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "deal_terms.schema.json").write_text(json.dumps(SCHEMA, indent=2), encoding="utf-8")
    for name, key in (("answers_thames.json", thames_key()), ("answers_rmbs.json", rmbs_key())):
        (OUT / name).write_text(json.dumps(key, indent=2, ensure_ascii=False), encoding="utf-8")
        from tar_agent.tools.extract import all_fields  # noqa: E402
        missing = [p for p, f in all_fields(key) if f["value"] is not None and f["page"] is None
                   and not p.endswith(".basis")]
        print(f"Wrote {OUT / name}: {len(all_fields(key))} fields, not located in the PDF: {missing}")
