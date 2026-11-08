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
    order = range(len(texts))
    if hint:
        order = [hint - 1] + [i for i in order if i != hint - 1]
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


def row(name, balance):
    """The anchor of a class row: its name followed by its balance, as the notes table writes it."""
    return f"{name} {balance:,.2f}" if balance != int(balance) else f"{name} {balance:,.0f}"


def thames_key():
    t = json.loads((ROOT / "data" / "deal_terms.json").read_text(encoding="utf-8"))
    md = (ROOT / "data" / "prospectus" / "prospectus.md").read_text(encoding="utf-8")
    pdf, d = THAMES_PDF, t["deal"]
    k = empty_terms()
    k["deal_name"] = keyed(d["issuer"], pdf, hint=1)
    k["currency"] = keyed(d["currency"], pdf, "currency", hint=2)
    k["pool_balance"] = keyed(t["initial_pool_balance"], pdf, hint=2)
    k["parties"] = {"issuer": keyed(d["issuer"], pdf, hint=2), "originator": keyed(d["originator"], pdf, hint=2),
                    "servicer": keyed(d["servicer"], pdf, hint=2), "trustee": keyed(d["trustee"], pdf, hint=2)}
    k["dates"] = {"cut_off": keyed(d["cut_off_date"], pdf, hint=2), "closing": keyed(d["closing_date"], pdf, hint=2),
                  "first_payment": keyed(d["first_payment_date"], pdf, hint=2)}
    total = sum(t["initial_note_balances"].values())
    anchors = {c["name"]: row(c["name"], t["initial_note_balances"][c["name"]]) for c in t["classes"]}
    k["classes"] = [{"name": keyed(c["name"], pdf, hint=3, anchor=anchors[c["name"]]),
                     "balance": keyed(t["initial_note_balances"][c["name"]], pdf, hint=3, anchor=anchors[c["name"]]),
                     "share": keyed(c["share"], pdf, hint=3, anchor=anchors[c["name"]]),
                     "margin": keyed(c["margin"], pdf, hint=3, anchor=anchors[c["name"]]),
                     "rating": keyed(c["rating"], pdf, hint=3, anchor=anchors[c["name"]])} for c in t["classes"]]
    pct = t["reserve_fund"]["required_pct_of_initial_notes"]
    k["reserve_funds"] = [{"name": keyed("Reserve fund", pdf, hint=9),
                           "amount": keyed(t["reserve_fund_required_amount"], pdf, hint=9, anchor="Reserve fund."),
                           "percent": keyed(pct, pdf, hint=9, anchor="Reserve fund."),
                           "basis": keyed(["A", "B", "C", "D"], pdf, hint=3),
                           "can_cover_losses": cover_keyed(t["reserve_fund"]["can_cover_losses"], "Reserve fund", pdf)}]
    section5 = md.split("# 5. Priority of payments")[1].split("\n# ")[0]
    labels = [re.sub(r"\.$", "", m) for m in re.findall(r"^\d+\. \*\*(.+?)\*\*", section5, flags=re.M)]
    k["priority_of_payments"]["combined"] = [keyed(x, pdf, hint=8) for x in labels]
    sched = [{"periods": f"{a} to {b}", "limit": lim} for a, b, lim in t["triggers"]["cum_default_schedule"]]
    k["triggers"] = [
        {"name": keyed("Cumulative default ratio", pdf, hint=9), "measure": keyed("cumulative default ratio", pdf, hint=9),
         "limit": keyed(sched, pdf, hint=9, anchor="Cumulative default ratio"),
         "consequence": keyed("sequentially", pdf, hint=9)},
        {"name": keyed("90+ day arrears ratio", pdf, hint=9), "measure": keyed("90+ day arrears ratio", pdf, hint=9),
         "limit": keyed(t["triggers"]["arrears_90_limit"], pdf, hint=9, anchor="90+ day arrears ratio"),
         "consequence": keyed("sequentially", pdf, hint=9)},
        {"name": keyed("Reserve fund", pdf, hint=9), "measure": keyed("reserve fund", pdf, hint=9),
         "limit": keyed("required amount", pdf, hint=9), "consequence": keyed("sequentially", pdf, hint=9)},
    ]
    criteria = md.split("met the following criteria at the cut-off date:")[1].split("\n\n")[1]
    k["eligibility_criteria"] = [keyed(re.sub(r"^\d+\. ", "", ln), pdf, hint=7) for ln in criteria.splitlines()]
    method = re.search(r"holds it as a \*(.+?)\*", md).group(1)
    k["risk_retention"] = keyed(method, pdf, hint=2)
    return k


def rmbs_key():
    pdf, d = RMBS_PDF, R.DEAL
    k = empty_terms()
    k["deal_name"] = keyed(d["issuer"], pdf, hint=1)
    k["currency"] = keyed(d["currency"], pdf, "currency", hint=2)
    k["pool_balance"] = keyed(d["pool_balance"], pdf, hint=2)
    k["parties"] = {"issuer": keyed(d["issuer"], pdf, hint=2), "originator": keyed(d["seller"], pdf, hint=2),
                    "servicer": keyed(d["mortgage_administrator"], pdf, hint=2), "trustee": keyed(d["trustee"], pdf, hint=2)}
    k["dates"] = {"cut_off": keyed(d["portfolio_reference_date"], pdf, hint=2),
                  "closing": keyed(d["issue_date"], pdf, hint=2),
                  "first_payment": keyed(d["first_interest_payment_date"], pdf, hint=2)}
    total = sum(c["balance"] for c in R.CLASSES)
    k["classes"] = [{"name": keyed(c["name"], pdf, hint=3, anchor=row(c["name"], c["balance"])),
                     "balance": keyed(c["balance"], pdf, hint=3, anchor=row(c["name"], c["balance"])),
                     "share": keyed(round(c["balance"] / total, 6), pdf, hint=3, anchor=row(c["name"], c["balance"])),
                     "margin": keyed(c["margin"], pdf, hint=3, anchor=row(c["name"], c["balance"]))
                     if c["margin"] is not None else field(None),
                     "rating": keyed(c["rating"], pdf, hint=3, anchor=row(c["name"], c["balance"]))} for c in R.CLASSES]
    k["reserve_funds"] = []
    for r in R.RESERVES:
        amount = round(r["percent"] * sum(c["balance"] for c in R.CLASSES if c["name"] in r["basis"]), 2)
        k["reserve_funds"].append({"name": keyed(r["name"], pdf, hint=4),
                                   "amount": keyed(amount, pdf, hint=4, anchor=r["name"]),
                                   "percent": keyed(r["percent"], pdf, hint=4, anchor=r["name"]),
                                   "basis": keyed(r["basis"], pdf, hint=4),
                                   "can_cover_losses": cover_keyed(r["can_cover_losses"], r["name"], pdf)})
    k["priority_of_payments"]["revenue"] = [keyed(x, pdf, hint=5) for x in R.REVENUE_PRIORITY]
    k["priority_of_payments"]["principal"] = [keyed(x, pdf, hint=6) for x in R.PRINCIPAL_PRIORITY]
    k["triggers"] = [{"name": keyed(t["name"], pdf, hint=7), "measure": keyed(t["measure"], pdf, hint=7),
                      "limit": keyed(t["limit"], pdf, hint=7, anchor=t["name"]), "consequence": keyed("Sequential Payment Trigger", pdf, hint=7)}
                     for t in R.TRIGGERS]
    k["eligibility_criteria"] = [keyed(w.rstrip("."), pdf, hint=10) for w in R.LOAN_WARRANTIES]
    k["risk_retention"] = keyed(R.RISK_RETENTION_METHOD, pdf, hint=12)
    k["definitions"] = {term: keyed(text, pdf, hint=13) for term, text in R.DEFINITIONS.items()}
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
