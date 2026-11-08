"""Final exam, section D: grade your new tool out of 30.

    python python/vol2/final_exam/grade.py                      grades candidate.py
    python python/vol2/final_exam/grade.py --module solution/reference.py

The expected values are computed here from the deal pack, never typed.
"""

import argparse
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))   # lets Python find tar_agent
from tar_agent.data import deal_terms, investor_report  # noqa: E402


def expected(period):
    pool = investor_report(period)["pool"]
    smm = pool["prepayments"] / (pool["opening_balance"] - pool["principal_received"])
    return {"pool_factor": pool["closing_balance"] / deal_terms()["initial_pool_balance"],
            "smm": smm, "cpr": 1 - (1 - smm) ** 12}


def load(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def grade(path):
    marks, lines = 0, []
    module = load(path)
    func = getattr(module, "pool_factor_and_cpr", None)
    try:
        shape_ok = set(func(1)) == {"period", "pool_factor", "smm", "cpr"}
    except Exception:
        shape_ok = False
    marks += 5 if shape_ok else 0
    lines.append(f"[{5 if shape_ok else 0}/5] returns a dictionary with the keys period, pool_factor, smm, cpr")
    for period in (1, 10, 12):
        try:
            got = func(period)
            want = expected(period)
            ok = got.get("period") == period and all(abs(got[k] - want[k]) < 1e-6 for k in want)
        except Exception as e:  # any crash loses the marks for this period
            ok, got = False, f"{type(e).__name__}: {e}"
        marks += 5 if ok else 0
        lines.append(f"[{5 if ok else 0}/5] values for period {period}" + ("" if ok else f" -> got {got}"))
    try:
        func(13)
        bad_ok = False
    except ValueError:
        bad_ok = True
    except Exception:
        bad_ok = False
    marks += 5 if bad_ok else 0
    lines.append(f"[{5 if bad_ok else 0}/5] period 13 raises ValueError")
    schema = getattr(module, "SCHEMA", {}) or {}
    fn = schema.get("function", {})
    params = fn.get("parameters", {})
    schema_ok = (schema.get("type") == "function" and fn.get("name") == "pool_factor_and_cpr"
                 and bool(fn.get("description")) and "period" in params.get("properties", {})
                 and params.get("required") == ["period"])
    marks += 5 if schema_ok else 0
    lines.append(f"[{5 if schema_ok else 0}/5] the schema names the tool, describes it and requires 'period'")
    return marks, lines


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", default="candidate.py", help="path relative to final_exam/")
    path = HERE / parser.parse_args().module
    total, report = grade(path)
    print("\n".join(report))
    print(f"Section D: {total}/30")
