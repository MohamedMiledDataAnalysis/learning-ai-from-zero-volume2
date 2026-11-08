"""Tool 6 — extract the deal terms from any prospectus PDF (Volume 2 Part E).

    extract_deal_terms(pdf_path, layer="rules")              # patterns only: reproducible, limited
    extract_deal_terms(pdf_path, layer="model", brain=brain)  # a model fills the schema, section by section
    extract_deal_terms(pdf_path, layer="both", brain=brain)   # rules first, the model fills the gaps

Every value comes back as a field:

    {"value": 62964482.91, "page": 3, "quote": "Class A £62,964,482.91 85% ...",
     "source": "rules", "grounded": true}

"grounded" is the result of the grounding check: true only if the value really appears on
the page it cites. A value that fails the check is kept, but flagged: the analyst must look.

The rules were written for the Thames prospectus, with a few common synonyms. On a
prospectus laid out differently they find only part of the terms; the coverage figure says
how much. That limit is the reason the model layer exists.
"""

import json
import re
from datetime import date, datetime

from .document import page_texts, read_pages, search_document

SCALARS = ["deal_name", "currency", "pool_balance", "parties.issuer", "parties.originator", "parties.servicer",
           "parties.trustee", "dates.cut_off", "dates.closing", "dates.first_payment", "risk_retention"]
LISTS = ["classes", "reserve_funds", "priority_of_payments", "triggers", "eligibility_criteria"]

PARTY_LABELS = {
    "issuer": ["Issuer"],
    "originator": ["Originator and seller", "Originator", "Seller"],
    "servicer": ["Servicer"],
    "trustee": ["Trustee"],
}
DATE_LABELS = {"cut_off": ["Cut-off date"], "closing": ["Closing date"], "first_payment": ["First payment date"]}
COMPANY = r"((?:[A-Z0-9][\w&'.-]* ){0,6}?(?:plc|PLC|Ltd|Limited|Society|LLP|Bank))\b"
DATE = r"(\d{4}-\d{2}-\d{2}|\d{1,2} [A-Z][a-z]+ \d{4})"
RETENTION_METHODS = ["vertical slice", "first loss tranche", "randomly selected exposures", "seller's share",
                     "originator's share"]


# ---------------------------------------------------------------- small helpers

def field(value=None, page=None, quote=None, source=None):
    return {"value": value, "page": page, "quote": quote, "source": source, "grounded": None}


def empty_terms():
    return {
        "deal_name": field(), "currency": field(), "pool_balance": field(),
        "parties": {k: field() for k in PARTY_LABELS},
        "dates": {k: field() for k in DATE_LABELS},
        "classes": [], "reserve_funds": [],
        "priority_of_payments": {"combined": [], "revenue": [], "principal": []},
        "triggers": [], "eligibility_criteria": [],
        "risk_retention": field(), "definitions": {},
    }


def money(text):
    return float(text.replace(",", ""))


def iso_date(text):
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return datetime.strptime(text, "%d %B %Y").date().isoformat()


def get(terms, path):
    node = terms
    for part in path.split("."):
        node = node[part]
    return node


def alnum(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def words(text):
    return set(re.findall(r"[a-z0-9]+", str(text).lower()))


# ---------------------------------------------------------------- layer 1: rules

def _search(texts, pattern, flags=0):
    """First match of a pattern on any page: (match, page number) or (None, None)."""
    for number, text in enumerate(texts, start=1):
        m = re.search(pattern, text, flags)
        if m:
            return m, number
    return None, None


def _numbered_items(lines, start_pattern):
    """The numbered list items ("1. ...", "2. ...") that follow the first line matching start_pattern."""
    for i, line in enumerate(lines):
        if re.search(start_pattern, line, re.IGNORECASE):
            items, started = [], False
            for line2 in lines[i + 1:]:
                m = re.match(r"^\d+\. (.+)$", line2)
                if m and not re.fullmatch(r"\d\. [A-Z][^.:]*", line2):      # "6. Reserve fund ..." is a heading
                    items.append(m.group(1))
                    started = True
                elif started and items and not items[-1].rstrip().endswith("."):
                    items[-1] += " " + line2                                 # the item continues on the next line
                elif started:
                    break
            return items
    return []


def extract_rules(pdf_path):
    """Layer 1: text patterns written for the Thames layout, with a few common synonyms."""
    pages = read_pages(pdf_path)
    texts = page_texts(pdf_path)
    terms = empty_terms()

    first = next((ln for ln in pages[0] if re.search(r"\b(plc|PLC|Limited|Ltd)$", ln)), None) if pages else None
    if first:
        terms["deal_name"] = field(first, 1, first, "rules")

    for key, labels in PARTY_LABELS.items():
        for label in labels:
            m, page = _search(texts, rf"\b{label} {COMPANY}")
            if m:
                terms["parties"][key] = field(m.group(1), page, m.group(0), "rules")
                break

    for key, labels in DATE_LABELS.items():
        for label in labels:
            m, page = _search(texts, rf"\b{label} {DATE}")
            if m:
                terms["dates"][key] = field(iso_date(m.group(1)), page, m.group(0), "rules")
                break

    m, page = _search(texts, r"\bCurrency [^()]*?\(?\b(GBP|EUR|USD)\b")
    if m:
        terms["currency"] = field(m.group(1), page, m.group(0), "rules")

    m, page = _search(texts, r"\bPool balance(?: at the cut-off date)? £([\d,]+\.\d\d)")
    if m:
        terms["pool_balance"] = field(money(m.group(1)), page, m.group(0), "rules")

    row = r"Class ([A-Z]) £([\d,]+(?:\.\d\d)?) (\d+(?:\.\d+)?)% SONIA \+ (\d+(?:\.\d+)?)% ([A-Z]{1,3}(?:sf)?)\b"
    for number, text in enumerate(texts, start=1):
        for m in re.finditer(row, text):
            q = m.group(0)
            terms["classes"].append({
                "name": field(m.group(1), number, q, "rules"),
                "balance": field(money(m.group(2)), number, q, "rules"),
                "share": field(round(float(m.group(3)) / 100, 6), number, q, "rules"),
                "margin": field(round(float(m.group(4)) / 100, 6), number, q, "rules"),
                "rating": field(m.group(5), number, q, "rules"),
            })

    pattern = r"\b((?:[A-Z][a-z]+ )?[Rr]eserve [Ff]und) of £([\d,]+(?:\.\d\d)?), equal to (\d+(?:\.\d+)?)% of the initial balance of the notes"
    for number, text in enumerate(texts, start=1):
        for m in re.finditer(pattern, text):
            q = m.group(0)
            name = m.group(1)[0].upper() + m.group(1)[1:]
            terms["reserve_funds"].append({
                "name": field(name, number, q, "rules"),
                "amount": field(money(m.group(2)), number, q, "rules"),
                "percent": field(round(float(m.group(3)) / 100, 6), number, q, "rules"),
                "basis": field(None),          # "the notes": every class (the rules do not read a list here)
                "can_cover_losses": _cover_field(name, texts),
            })

    for number, lines in enumerate(pages, start=1):
        items = _numbered_items(lines, r"^\d+\. Priority of payments$")
        if items:
            for item in items:
                label = re.split(r"[:.]", item, maxsplit=1)[0].strip()
                terms["priority_of_payments"]["combined"].append(field(label, number, item, "rules"))
            break

    for number, text in enumerate(texts, start=1):
        for m in re.finditer(r"Test \d — ([^.]+)\. (.*?)(?=Test \d —|Consequence\.|$)", text):
            name, body = m.group(1), m.group(2)
            schedule = re.findall(r"Periods (\d+) to (\d+) (\d+(?:\.\d+)?)%", body)
            single = re.search(r"must not exceed (\d+(?:\.\d+)?)%", body)
            if schedule:
                limit = [{"periods": f"{a} to {b}", "limit": round(float(p) / 100, 6)} for a, b, p in schedule]
            elif single:
                limit = round(float(single.group(1)) / 100, 6)
            elif "required amount" in body:
                limit = "required amount"
            else:
                limit = None
            consequence = re.search(r"Consequence\. (.+?\.)", text)
            q = m.group(0).strip()
            terms["triggers"].append({
                "name": field(name, number, q, "rules"),
                "measure": field(name.lower(), number, q, "rules"),
                "limit": field(limit, number, q, "rules"),
                "consequence": field(consequence.group(1) if consequence else None, number,
                                     consequence.group(0) if consequence else None, "rules"),
            })

    for number, lines in enumerate(pages, start=1):
        items = _numbered_items(lines, r"met the following criteria|eligibility criteria:")
        if items:
            terms["eligibility_criteria"] = [field(it, number, it, "rules") for it in items]
            break

    for number, text in enumerate(texts, start=1):
        for sentence in re.split(r"(?<=\.) ", text):
            if re.search(r"\bretain", sentence) or "Risk retention" in sentence:
                method = next((x for x in RETENTION_METHODS if x in sentence), None)
                if method:
                    terms["risk_retention"] = field(method, number, sentence, "rules")
                    break
        if terms["risk_retention"]["value"]:
            break

    for number, lines in enumerate(pages, start=1):
        if not any("Definitions" in line for line in lines):
            continue
        for line in lines:
            m = re.match(r"^• ([A-Z][^:]{2,40}): (.+)$", line)
            if m:
                terms["definitions"][m.group(1)] = field(m.group(2), number, line, "rules")
    return terms


# ---------------------------------------------------------------- layer 2: a model, section by section

SYSTEM_PROMPT = (
    "You extract the terms of a securitisation from passages of its prospectus. Reply with JSON only, no other "
    "text. Use only the passages given. For every value give the page number of the passage it comes from and "
    "copy the exact sentence or table row as the quote. If a value is not in the passages, use null. Write "
    "percentages as decimals (0.58% becomes 0.0058), amounts as plain numbers without commas or currency signs, "
    "and dates as YYYY-MM-DD. For a reserve fund, can_cover_losses is true when the prospectus says it can pay "
    "principal or cure a principal deficiency, false when it pays only fees and interest. "
    "Each field is an object: {\"value\": ..., \"page\": ..., \"quote\": ...}.")

F = '{"value": ..., "page": ..., "quote": ...}'
SECTIONS = [
    ("overview", "issuer seller originator servicer administrator trustee cut-off reference closing issue date "
                 "first payment currency sterling pool balance aggregate",
     '{"deal_name": F, "parties": {"issuer": F, "originator": F, "servicer": F, "trustee": F}, '
     '"dates": {"cut_off": F, "closing": F, "first_payment": F}, "currency": F, "pool_balance": F}'),
    ("classes", "notes class principal amount margin SONIA rating",
     '{"classes": [{"name": F, "balance": F, "share": F, "margin": F, "rating": F}]}'),
    ("reserve_funds", "reserve fund required amount per cent notes principal deficiency interest only",
     '{"reserve_funds": [{"name": F, "amount": F, "percent": F, "basis": F, "can_cover_losses": F}]}'),
    ("priority_of_payments", "priority of payments order item paid",
     '{"priority_of_payments": {"combined": [F], "revenue": [F], "principal": [F]}}'),
    ("triggers", "trigger event test exceeds per cent sequential limit",
     '{"triggers": [{"name": F, "measure": F, "limit": F, "consequence": F}]}'),
    ("eligibility", "eligibility criteria warranties each loan",
     '{"eligibility_criteria": [F]}'),
    ("risk_retention", "risk retention retains 5 per cent net economic interest",
     '{"risk_retention": F}'),
]


def section_prompt(pdf_path, name, query, template, top_k=4):
    passages = search_document(pdf_path, query, top_k=top_k)["results"]
    text = "\n\n".join(f"[page {p['page']}] {p['text']}" for p in passages)
    return (f"SECTION: {name}\nFill this JSON template, where F means {F}:\n{template.replace('F', F)}\n\n"
            f"Passages:\n{text}")


def _parse_reply(content, name):
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("the reply is not a JSON object")
    expected = {"overview": ["deal_name"], "eligibility": ["eligibility_criteria"]}.get(name, [name])
    for key in expected:
        if key not in data:
            raise ValueError(f"the reply has no '{key}' key")
    return data


def _as_field(x):
    if isinstance(x, dict) and "value" in x:
        page = x.get("page")
        try:
            page = int(page) if page is not None else None
        except (TypeError, ValueError):
            page = None
        return field(x.get("value"), page, x.get("quote"), "model")
    return field(x, None, None, "model") if x is not None else field()


def _merge_section(terms, name, data):
    if name == "overview":
        terms["deal_name"] = _as_field(data.get("deal_name"))
        terms["currency"] = _as_field(data.get("currency"))
        terms["pool_balance"] = _as_field(data.get("pool_balance"))
        for k in PARTY_LABELS:
            terms["parties"][k] = _as_field((data.get("parties") or {}).get(k))
        for k in DATE_LABELS:
            terms["dates"][k] = _as_field((data.get("dates") or {}).get(k))
    elif name in ("classes", "reserve_funds", "triggers"):
        terms[name] = [{k: _as_field(v) for k, v in item.items()} for item in data.get(name) or []]
    elif name == "priority_of_payments":
        pop = data.get(name) or {}
        terms[name] = {k: [_as_field(x) for x in pop.get(k) or []] for k in ("combined", "revenue", "principal")}
    elif name == "eligibility":
        terms["eligibility_criteria"] = [_as_field(x) for x in data.get("eligibility_criteria") or []]
    elif name == "risk_retention":
        terms["risk_retention"] = _as_field(data.get("risk_retention"))


def extract_model(pdf_path, brain):
    """Layer 2: ask a brain to fill the schema, one section at a time, from the best passages of the PDF."""
    terms = empty_terms()
    log = []
    for name, query, template in SECTIONS:
        memory = [{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": section_prompt(pdf_path, name, query, template)}]
        for attempt in (1, 2):
            reply = brain.next(memory, [])
            try:
                _merge_section(terms, name, _parse_reply(reply.get("content", ""), name))
                log.append({"section": name, "attempts": attempt, "ok": True})
                break
            except (ValueError, json.JSONDecodeError, AttributeError, TypeError) as e:
                if attempt == 2:
                    log.append({"section": name, "attempts": 2, "ok": False, "error": str(e)})
                else:
                    memory += [{"role": "assistant", "content": reply.get("content", "")},
                               {"role": "user", "content": f"Your reply was not valid for this section: {e}. "
                                                           "Reply again with the JSON only."}]
    terms["model_log"] = log
    return terms


# ---------------------------------------------------------------- what a reserve fund can pay

def reads_cover(sentence):
    """What a sentence says a reserve fund can pay: True (principal or losses), False (only fees and
    interest), or None (the sentence does not say).

    "never used to pay principal" and "covers ... interest ... only" read False; "principal deficiency",
    "pay principal" or "losses" without a negation read True.
    """
    s = " ".join(sentence.lower().split())
    if re.search(r"\b(never|not|cannot)\b[^.]*\bprincipal\b", s):
        return False
    if re.search(r"principal deficiency|pay principal|principal on the notes|\blosses\b", s):
        return True
    if re.search(r"\binterest\b", s) and re.search(r"\bonly\b", s):
        return False
    return None


def _cover_field(name, texts):
    """The first sentence whose subject is the reserve fund ("The General Reserve Fund covers ...") and that
    says what it can pay, as a grounded field. Only sentences that start with the fund's own name count:
    a table row or a sentence about another fund cannot decide it."""
    pattern = r"\bThe " + re.escape(name) + r"\b[^.;]*[.;]"
    for number, text in enumerate(texts, start=1):
        for m in re.finditer(pattern, " ".join(text.split()), flags=re.IGNORECASE):
            sentence = m.group(0)
            if reads_cover(sentence) is not None:
                return field(reads_cover(sentence), number, sentence, "rules")
    return field(None)


# ---------------------------------------------------------------- the grounding check

def _candidates(value):
    """The ways a value can be written in a prospectus."""
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        v = float(value)
        if 0 < abs(v) < 1:
            p = v * 100
            forms = {f"{p:.2f}", f"{p:.3f}".rstrip("0"), f"{p:g}"}
            return sorted({f + s for f in forms for s in ("%", " per cent")} | {f"{p:.2f}"})
        out = {f"{v:,.2f}", f"{v:.2f}"}
        if v == int(v):
            out |= {f"{v:,.0f}", f"{v:.0f}"}
        return sorted(out)
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        d = date.fromisoformat(text)
        return [text, f"{d.day} {d.strftime('%B')} {d.year}"]
    return [text]


def _number_in(candidate, text):
    """A number written in the text as a whole number: "2.50" is not found inside "12.50" or "2.505"."""
    return re.search(r"(?<![0-9])(?<![0-9][.,])" + re.escape(candidate) + r"(?![0-9])(?![.,][0-9])", text) is not None


def _value_on_page(value, page_text, key=""):
    if isinstance(value, list):
        # A schedule of limits ([{"periods": ..., "limit": ...}]) or a list of class names (["A", "B"]).
        parts = [x.get("limit") if isinstance(x, dict) else x for x in value]
        return all(_value_on_page(p, page_text) for p in parts) if parts else False
    if key == "currency" and str(value) == "GBP":
        return any(w in page_text for w in ("GBP", "sterling", "Sterling", "£"))
    for c in _candidates(value):
        if isinstance(value, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            if alnum(c) and alnum(c) in alnum(page_text):
                return True
        elif _number_in(c, page_text):
            return True
    return False


def ground_field(f, texts, key=""):
    if f["value"] is None:
        f["grounded"] = None
        return f
    p = f.get("page")
    if not isinstance(p, int) or not 1 <= p <= len(texts):
        f["grounded"] = False
        return f
    page_text = texts[p - 1]
    if isinstance(f["value"], bool):
        # A yes/no value is never written as such: its quote must be on the page and must say the same thing.
        q = f.get("quote") or ""
        f["grounded"] = bool(q) and words(q) <= words(page_text) and reads_cover(q) is f["value"]
        return f
    value_ok = _value_on_page(f["value"], page_text, key)
    # A quote counts when all its words are on the page, in any order: PDF libraries order the cells
    # of a table differently (pypdf and pdftools disagree on the Severn tables), the words stay the same.
    quote_ok = not f.get("quote") or words(f["quote"]) <= words(page_text)
    # A number or a date must also be written in its own quote: a quote from the right page about another
    # figure (the reserve fund sentence cited for a trigger limit) does not support the value.
    v = f["value"]
    if f.get("quote") and ((isinstance(v, (int, float)) and not isinstance(v, bool))
                           or (isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v))):
        quote_ok = quote_ok and _value_on_page(v, f["quote"], key)
    f["grounded"] = bool(value_ok and quote_ok)
    return f


def all_fields(terms):
    """Every field of the terms, with a readable path: ('classes[0].margin', field)."""
    out = []
    for path in SCALARS:
        out.append((path, get(terms, path)))
    for i, c in enumerate(terms["classes"]):
        out += [(f"classes[{i}].{k}", v) for k, v in c.items()]
    for i, r in enumerate(terms["reserve_funds"]):
        out += [(f"reserve_funds[{i}].{k}", v) for k, v in r.items()]
    for kind in ("combined", "revenue", "principal"):
        out += [(f"priority_of_payments.{kind}[{i}]", v) for i, v in enumerate(terms["priority_of_payments"][kind])]
    for i, t in enumerate(terms["triggers"]):
        out += [(f"triggers[{i}].{k}", v) for k, v in t.items()]
    out += [(f"eligibility_criteria[{i}]", v) for i, v in enumerate(terms["eligibility_criteria"])]
    out += [(f"definitions.{k}", v) for k, v in terms["definitions"].items()]
    return out


def ground_terms(terms, pdf_path):
    """Run the grounding check on every field; return the paths that failed it."""
    texts = page_texts(pdf_path)
    failed = []
    for path, f in all_fields(terms):
        ground_field(f, texts, key=path)
        if f["grounded"] is False:
            failed.append(path)
    return failed


# ---------------------------------------------------------------- coverage, combining the layers, the tool

def _found(terms, path):
    if path in LISTS:
        node = terms[path]
        if path == "priority_of_payments":
            return any(node[k] for k in node)
        return bool(node)
    return get(terms, path)["value"] is not None


def coverage(terms):
    """How much of the schema was filled: 11 single fields plus 5 lists (a list counts when it is not empty)."""
    slots = SCALARS + LISTS
    found = [s for s in slots if _found(terms, s)]
    return {"schema_fields": len(slots), "found": len(found), "share": round(len(found) / len(slots), 4),
            "missing": [s for s in slots if s not in found]}


def combine(rules, model):
    """Both layers: keep every rules value; the model fills only what the rules did not find."""
    out = json.loads(json.dumps(rules))
    for path in SCALARS:
        if get(out, path)["value"] is None and get(model, path)["value"] is not None:
            parent, _, key = path.rpartition(".")
            (get(out, parent) if parent else out)[key] = get(model, path)
    for name in ("classes", "reserve_funds", "triggers", "eligibility_criteria"):
        if not out[name] and model[name]:
            out[name] = model[name]
    if not any(out["priority_of_payments"].values()):
        out["priority_of_payments"] = model["priority_of_payments"]
    out["model_log"] = model.get("model_log", [])
    return out


def extract_deal_terms(pdf_path, layer="rules", brain=None):
    """Tool entry point: the deal terms of any prospectus PDF, each value with its page, quote and grounding."""
    if layer not in ("rules", "model", "both"):
        raise ValueError("layer must be 'rules', 'model' or 'both'")
    if layer in ("model", "both") and brain is None:
        raise ValueError(f"layer '{layer}' needs a brain (rules, replay, live or record)")
    if layer == "rules":
        terms = extract_rules(pdf_path)
    elif layer == "model":
        terms = extract_model(pdf_path, brain)
    else:
        terms = combine(extract_rules(pdf_path), extract_model(pdf_path, brain))
    failed = ground_terms(terms, pdf_path)
    terms["layer"] = layer
    terms["coverage"] = coverage(terms)
    terms["ungrounded"] = failed
    return terms


# ---------------------------------------------------------------- scoring against an answer key (tests, book)

def _same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(float(a) - float(b)) <= max(0.005, 1e-6 * abs(float(b)))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x.get("limit"), y.get("limit")) for x, y in zip(a, b))
    return a is not None and b is not None and alnum(a) == alnum(b)


def score_against_key(terms, key):
    """Field-by-field comparison with an answer key: how many expected values were found, and how many are right."""
    rows = []

    def add(path, got, expected):
        rows.append({"field": path, "found": got is not None, "correct": _same(got, expected)})

    for path in SCALARS:
        add(path, get(terms, path)["value"], get(key, path)["value"])
    got_classes = {alnum(c["name"]["value"]): c for c in terms["classes"] if c["name"]["value"] is not None}
    for c in key["classes"]:
        g = got_classes.get(alnum(c["name"]["value"]))
        for k in ("balance", "share", "margin", "rating"):
            if c[k]["value"] is not None:
                add(f"classes.{c['name']['value']}.{k}", g[k]["value"] if g else None, c[k]["value"])
    got_res = {alnum(r["name"]["value"]): r for r in terms["reserve_funds"] if r["name"]["value"] is not None}
    for r in key["reserve_funds"]:
        g = got_res.get(alnum(r["name"]["value"]))
        for k in ("amount", "percent", "can_cover_losses"):
            if k in r:
                add(f"reserve_funds.{r['name']['value']}.{k}",
                    g[k]["value"] if g and k in g else None, r[k]["value"])
    for kind in ("combined", "revenue", "principal"):
        got = {alnum(x["value"]) for x in terms["priority_of_payments"][kind] if x["value"] is not None}
        for x in key["priority_of_payments"][kind]:
            v = x["value"]
            add(f"priority_of_payments.{kind}.{v}", v if alnum(v) in got else None, v)
    got_tr = {alnum(t["name"]["value"]): t for t in terms["triggers"] if t["name"]["value"] is not None}
    for t in key["triggers"]:
        g = got_tr.get(alnum(t["name"]["value"]))
        add(f"triggers.{t['name']['value']}.name", t["name"]["value"] if g else None, t["name"]["value"])
        add(f"triggers.{t['name']['value']}.limit", g["limit"]["value"] if g else None, t["limit"]["value"])
    got_el = {alnum(x["value"]) for x in terms["eligibility_criteria"] if x["value"] is not None}
    for i, x in enumerate(key["eligibility_criteria"], start=1):
        add(f"eligibility_criteria.{i}", x["value"] if alnum(x["value"]) in got_el else None, x["value"])
    found = sum(r["found"] for r in rows)
    correct = sum(r["correct"] for r in rows)
    return {"fields": len(rows), "found": found, "correct": correct,
            "found_share": round(found / len(rows), 4), "correct_share": round(correct / len(rows), 4),
            "rows": rows}
