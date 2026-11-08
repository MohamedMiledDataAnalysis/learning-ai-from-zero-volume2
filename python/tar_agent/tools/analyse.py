"""Tool 7 — analyse extracted deal terms (Volume 2 Part E).

analyse_deal_terms(terms) takes the output of extract_deal_terms and computes what an
analyst checks first on a new deal:

- the credit enhancement of each class: the notes ranking below it (subordination) plus
  the reserve funds that can absorb its losses, as shares of all the notes. A reserve counts
  by what the prospectus says it can pay, never by its name: it counts only when it can pay
  principal or cover losses (can_cover_losses is True, for example it can cure a principal
  deficiency). A reserve that pays only fees and interest is liquidity support and does not
  count; a reserve whose purpose was not found is not counted either, and the output says so.
  A reserve sized on a list of classes (its basis) supports only those classes (Severn's
  General Reserve Fund is sized on Classes A to D and does not cover Class Z); a reserve with
  no basis supports every class;
- five consistency checks, each passed (True), failed (False) or not possible (None)
  because a value is missing;
- the priority of payments as a plain list, for the waterfall diagram of the apps.
"""


def _v(f):
    return f["value"] if isinstance(f, dict) else None


def credit_enhancement(terms):
    classes = [c for c in terms["classes"] if isinstance(_v(c["balance"]), (int, float))]
    total = sum(_v(c["balance"]) for c in classes)
    if not total:
        return []
    loss_reserves = [r for r in terms["reserve_funds"]
                     if isinstance(_v(r["amount"]), (int, float)) and _v(r.get("can_cover_losses")) is True]

    def supports(reserve, name):
        basis = _v(reserve.get("basis"))
        return not isinstance(basis, list) or not basis or name in basis

    rows = []
    for i, c in enumerate(classes):
        below = sum(_v(x["balance"]) for x in classes[i + 1:])
        reserves = sum(_v(r["amount"]) for r in loss_reserves if supports(r, _v(c["name"])))
        rows.append({
            "class": _v(c["name"]),
            "balance": _v(c["balance"]),
            "share_of_notes": round(_v(c["balance"]) / total, 6),
            "subordination": round(below / total, 6),
            "reserve_support": round(reserves / total, 6),
            "credit_enhancement": round((below + reserves) / total, 6),
            "margin": _v(c["margin"]),
            "rating": _v(c["rating"]),
        })
    return rows


def reserve_treatment(terms):
    """For each reserve fund: counted in credit enhancement or not, and why."""
    out = []
    for r in terms["reserve_funds"]:
        cover = _v(r.get("can_cover_losses"))
        if cover is True:
            reason = "counted: it can pay principal or cover losses"
        elif cover is False:
            reason = "not counted: it pays only fees and interest (liquidity support)"
        else:
            reason = "reserve not counted: what it can pay was not found"
        out.append({"name": _v(r["name"]), "amount": _v(r["amount"]), "counted": cover is True, "reason": reason})
    return out


def _basis_total(reserve, classes):
    basis = _v(reserve.get("basis"))
    if not isinstance(basis, list) or not basis:
        return sum(_v(c["balance"]) for c in classes if isinstance(_v(c["balance"]), (int, float)))
    return sum(_v(c["balance"]) for c in classes
               if _v(c["name"]) in basis and isinstance(_v(c["balance"]), (int, float)))


def consistency_checks(terms, ce):
    checks = []

    def add(name, passed, detail):
        checks.append({"check": name, "passed": passed, "detail": detail})

    pool = _v(terms["pool_balance"])
    notes = sum(r["balance"] for r in ce)
    if pool is None or not ce:
        add("classes add up to the pool", None, "pool balance or classes missing")
    else:
        add("classes add up to the pool", abs(notes - pool) <= 1.0,
            f"notes {notes:,.2f} against pool {pool:,.2f} (difference {notes - pool:,.2f})")

    margins = [r["margin"] for r in ce if isinstance(r["margin"], (int, float))]
    if len(margins) < 2:
        add("margins rise as seniority falls", None, "fewer than two margins")
    else:
        add("margins rise as seniority falls", all(a <= b for a, b in zip(margins, margins[1:])),
            " < ".join(f"{m * 100:.2f}%" for m in margins))

    ces = [r["credit_enhancement"] for r in ce]
    if len(ces) < 2:
        add("credit enhancement highest for Class A", None, "fewer than two classes")
    else:
        add("credit enhancement highest for Class A", all(a > b for a, b in zip(ces, ces[1:])),
            " > ".join(f"{r['class']} {r['credit_enhancement'] * 100:.2f}%" for r in ce))

    res = [r for r in terms["reserve_funds"] if isinstance(_v(r["amount"]), (int, float))
           and isinstance(_v(r["percent"]), (int, float))]
    if not res or not ce:
        add("reserve funds match their percentage", None, "no reserve fund with both an amount and a percentage")
    else:
        details, ok = [], True
        for r in res:
            expected = _v(r["percent"]) * _basis_total(r, terms["classes"])
            good = abs(expected - _v(r["amount"])) <= 1.0
            ok = ok and good
            details.append(f"{_v(r['name'])}: {_v(r['amount']):,.2f} against {expected:,.2f}")
        add("reserve funds match their percentage", ok, "; ".join(details))

    if not terms["triggers"]:
        add("every trigger has a limit", None, "no trigger found")
    else:
        missing = [str(_v(t["name"])) for t in terms["triggers"] if _v(t["limit"]) is None]
        add("every trigger has a limit", not missing, "missing: " + ", ".join(missing) if missing else "all have one")
    return checks


def waterfall(terms):
    pop = terms["priority_of_payments"]
    if pop["revenue"] or pop["principal"]:
        return {"type": "separate", "revenue": [_v(x) for x in pop["revenue"]],
                "principal": [_v(x) for x in pop["principal"]]}
    return {"type": "combined", "combined": [_v(x) for x in pop["combined"]]}


def analyse_deal_terms(terms):
    """Tool entry point: credit enhancement per class, consistency checks and the waterfall list."""
    ce = credit_enhancement(terms)
    checks = consistency_checks(terms, ce)
    return {
        "deal": _v(terms["deal_name"]),
        "credit_enhancement": ce,
        "reserves": reserve_treatment(terms),
        "checks": checks,
        "checks_passed": sum(c["passed"] is True for c in checks),
        "checks_failed": sum(c["passed"] is False for c in checks),
        "checks_not_possible": sum(c["passed"] is None for c in checks),
        "waterfall": waterfall(terms),
        "ungrounded_values": len(terms.get("ungrounded", [])),
    }
