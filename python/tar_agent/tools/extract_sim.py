"""A stand-in for a model, for the tests and the book's reproducible runs of the model layer.

simulated_model_brain(answer_key) is a RuleBrain: it reads which section the prompt asks for
("SECTION: classes") and replies with the JSON a perfect model would write, taken from the
answer key. It is NOT a language model and the book labels its runs "simulated". Its purpose
is to exercise everything around the model (the prompts, the JSON parsing, the retry, the
merging and the grounding check) with replies that are the same on every computer.

plant={"classes.B.margin": 0.018} makes it write one wrong value, the way a real model can,
so the grounding check can be seen catching it.
"""

import json

from agent_core.brains import RuleBrain


def _plain(f):
    return {"value": f["value"], "page": f["page"], "quote": f["quote"]}


def section_reply(key, name, plant=None):
    plant = plant or {}
    if name == "overview":
        data = {"deal_name": _plain(key["deal_name"]), "currency": _plain(key["currency"]),
                "pool_balance": _plain(key["pool_balance"]),
                "parties": {k: _plain(v) for k, v in key["parties"].items()},
                "dates": {k: _plain(v) for k, v in key["dates"].items()}}
    elif name == "classes":
        data = {"classes": []}
        for c in key["classes"]:
            row = {k: _plain(v) for k, v in c.items()}
            for k in row:
                path = f"classes.{c['name']['value']}.{k}"
                if path in plant:
                    row[k]["value"] = plant[path]
            data["classes"].append(row)
    elif name == "reserve_funds":
        data = {"reserve_funds": [{k: _plain(v) for k, v in r.items()} for r in key["reserve_funds"]]}
    elif name == "priority_of_payments":
        data = {"priority_of_payments": {k: [_plain(x) for x in v] for k, v in key["priority_of_payments"].items()}}
    elif name == "triggers":
        data = {"triggers": [{k: _plain(v) for k, v in t.items()} for t in key["triggers"]]}
    elif name == "eligibility":
        data = {"eligibility_criteria": [_plain(x) for x in key["eligibility_criteria"]]}
    else:
        data = {"risk_retention": _plain(key["risk_retention"])}
    return json.dumps(data, ensure_ascii=False)


def simulated_model_brain(answer_key, plant=None):
    def rules(memory):
        prompt = next(m["content"] for m in reversed(memory) if m["role"] == "user" and "SECTION:" in m["content"])
        name = prompt.split("SECTION:", 1)[1].split("\n", 1)[0].strip()
        return {"content": section_reply(answer_key, name, plant), "tool_calls": []}
    return RuleBrain(rules)
