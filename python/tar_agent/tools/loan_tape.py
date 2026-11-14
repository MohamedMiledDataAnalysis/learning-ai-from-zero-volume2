"""Tool 1 — load and validate the loan tape.

The originator sends a loan tape: one row per loan. Before closing, Kestrel makes it
available in the FCA template for car loans (fields AUTL1 to AUTL84), with a
supplementary file for the fields the template does not have, and a data dictionary.
Before using the tape, an analyst checks it. This tool reads the tape through the
dictionary, runs the checks, lists every problem it finds, and can return a cleaned
copy with the safe fixes applied.

Each check is a small rule. A rule never guesses: when the correct value cannot
be known (an impossible credit score), the value is set to missing and flagged.
"""

import difflib
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..data import DATA_DIR, STANDARD_REGIONS, deal_terms

REQUIRED = ["loan_id", "origination_date", "maturity_date", "original_balance", "current_balance",
            "interest_rate_pct", "credit_score", "region", "postcode_area"]


POOL_CUT = DATA_DIR / "originator" / "THAMES_2026-1_AUTL_Pool_Cut_2025-12-31.csv"
SUPPLEMENTARY = DATA_DIR / "originator" / "Kestrel_Thames_2026-1_Supplementary_Data_2025-12-31.csv"
DICTIONARY = DATA_DIR / "originator" / "Kestrel_Thames_2026-1_Data_Dictionary.xlsx"

# The working name of each column, and where it comes from: a field of the FCA template, or a field of the
# supplementary file. Columns marked "code" hold a list code that the dictionary's "List Codes" sheet decodes.
TAPE_SOURCES = [
    ("loan_id", "AUTL2", "text"), ("origination_date", "AUTL24", "text"), ("maturity_date", "AUTL25", "text"),
    ("original_term_months", "AUTL26", "integer"), ("remaining_term_months", None, "integer"),
    ("product", "AUTL23", "code"), ("vehicle_type", "AUTL56", "code"), ("fuel_type", "Fuel Type", "text"),
    ("vehicle_value", "AUTL60", "number"), ("original_balance", "AUTL29", "number"),
    ("current_balance", "AUTL30", "number"), ("balloon_amount", "AUTL38", "number"),
    ("ltv_original_pct", "AUTL59", "number"), ("interest_rate_pct", "AUTL40", "number"),
    ("monthly_instalment", "AUTL37", "number"), ("credit_score", "Bureau Score at Origination", "integer"),
    ("employment_status", "AUTL12", "code"), ("annual_income", "AUTL16", "number"), ("region", "Region", "text"),
    ("postcode_area", "Postcode Area", "text"), ("days_past_due", "AUTL69", "integer"),
]


def read_dictionary(sheet, path=None):
    """One sheet of the originator's data dictionary."""
    return pd.read_excel(path or DICTIONARY, sheet_name=sheet, dtype=str, keep_default_na=False)


def read_tape(path=None, supplementary=None):
    """Read the cut-off loan tape exactly as received, with working column names.

    The tape is the FCA template file (fields AUTL1 to AUTL84). Its columns must be the dictionary's field codes,
    in order. The fields the template does not have come from the supplementary file, joined on AUTL2. List codes
    (HIRP, NEWX, EMUK, ...) become the originator's own values through the dictionary. Empty cells stay empty
    strings, so a missing value is visible. A CSV file already in working names is read as it is.
    """
    path = Path(path) if path else POOL_CUT
    tape = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[])
    if "loan_id" in tape.columns:                                 # already in working names
        return pd.read_csv(path, keep_default_na=False, na_values=[])
    codes = list(read_dictionary("FCA Template AUTL")["Field Code"])
    if list(tape.columns) != codes:
        raise ValueError(f"{path.name} does not follow the FCA template: expected the fields AUTL1 to AUTL84 in "
                         f"order, found {list(tape.columns)[:3]}...")
    extra = pd.read_csv(supplementary or SUPPLEMENTARY, dtype=str, keep_default_na=False, na_values=[])
    tape = tape.merge(extra, on="AUTL2", how="left").fillna("")      # duplicated rows stay duplicated
    lists = read_dictionary("List Codes")
    decode = {(f, c): v for f, c, v in zip(lists["Field Code"], lists["Code"], lists["Kestrel Value"])}
    out = pd.DataFrame()
    for name, source, kind in TAPE_SOURCES:
        if name == "remaining_term_months":                          # term less the instalments already paid
            out[name] = tape.AUTL26.astype(int) - tape.AUTL47.astype(int)
        elif kind == "code":
            out[name] = [decode.get((source, c), c) for c in tape[source]]
        elif kind == "number":
            out[name] = tape[source].astype(float)
        elif kind == "integer":
            out[name] = tape[source].astype(int)
        else:
            out[name] = tape[source]
    return out


def find_issues(tape):
    """Run every rule and return a list of issues (one dictionary per problem)."""
    issues = []

    def add(row, column, value, rule, fix):
        issues.append({"loan_id": row["loan_id"], "column": column, "value": value, "rule": rule, "fix": fix})

    # Rule 1: a row that appears twice.
    for _, row in tape[tape.duplicated(keep="first")].iterrows():
        add(row, "(whole row)", "", "duplicate row", "drop the second copy")
    # Rule 2: the same loan_id on two different rows.
    dup_ids = tape.drop_duplicates()
    for _, row in dup_ids[dup_ids.loan_id.duplicated()].iterrows():
        add(row, "loan_id", row["loan_id"], "loan_id used by two different rows", "ask the originator")

    for _, row in tape.drop_duplicates().iterrows():
        # Rule 3: required fields must not be empty.
        for col in REQUIRED:
            if str(row[col]).strip() == "":
                add(row, col, "", "missing value", "leave missing and flag")
        # Rule 4: balances must be positive and not above the amount lent.
        if row["current_balance"] < 0:
            add(row, "current_balance", row["current_balance"], "negative balance", "take the absolute value")
        elif row["current_balance"] > row["original_balance"]:
            add(row, "current_balance", row["current_balance"], "balance above the amount lent", "ask the originator")
        # Rule 5: interest rates between 0% and 30%.
        rate = row["interest_rate_pct"]
        if not 0 < rate <= 30:
            if 100 < rate <= 3000:
                add(row, "interest_rate_pct", rate, "rate out of range (decimal point missing)", "divide by 100")
            else:
                add(row, "interest_rate_pct", rate, "rate out of range", "ask the originator")
        # Rule 6: credit scores are on a 0-999 scale.
        if not 0 <= row["credit_score"] <= 999:
            add(row, "credit_score", row["credit_score"], "credit score outside 0-999", "set to missing and flag")
        # Rule 7: a loan matures after it starts.
        if row["maturity_date"] <= row["origination_date"]:
            add(row, "origination_date/maturity_date", f"{row['origination_date']}/{row['maturity_date']}",
                "maturity date not after origination date", "swap the two dates")
        # Rule 8: regions must use the standard names.
        if row["region"] not in STANDARD_REGIONS:
            match = difflib.get_close_matches(row["region"].title(), STANDARD_REGIONS, n=1, cutoff=0.8)
            fix = f"replace with '{match[0]}'" if match else "ask the originator"
            add(row, "region", row["region"], "region not a standard name", fix)
        # Rule 9: eligibility criterion — no arrears at the cut-off date.
        if row["days_past_due"] != 0:
            add(row, "days_past_due", row["days_past_due"], "loan in arrears at cut-off (not eligible)",
                "ask the originator")
    return issues


def clean_tape(tape, issues):
    """Apply the safe fixes. Issues whose fix is 'ask the originator' are left unchanged."""
    out = tape.drop_duplicates().copy().reset_index(drop=True)
    out["credit_score"] = out["credit_score"].astype("Int64")
    for issue in issues:
        i = out.index[out.loan_id == issue["loan_id"]]
        col, fix = issue["column"], issue["fix"]
        if fix == "take the absolute value":
            out.loc[i, col] = out.loc[i, col].abs()
        elif fix == "divide by 100":
            out.loc[i, col] = (out.loc[i, col] / 100).round(2)
        elif fix == "set to missing and flag":
            out.loc[i, col] = pd.NA
        elif fix == "swap the two dates":
            o, m = out.loc[i, "origination_date"].copy(), out.loc[i, "maturity_date"].copy()
            out.loc[i, "origination_date"], out.loc[i, "maturity_date"] = m.values, o.values
        elif fix.startswith("replace with"):
            out.loc[i, col] = fix.split("'")[1]
    return out


def validate_loan_tape(path=None, supplementary=None):
    """Tool entry point. Returns a summary the model can read, without the 5,000 rows."""
    tape = read_tape(path, supplementary)
    issues = find_issues(tape)
    cleaned = clean_tape(tape, issues)
    expected = deal_terms()["initial_pool_balance"]
    total = round(float(cleaned.current_balance.sum()), 2)
    by_rule = {}
    for issue in issues:
        by_rule[issue["rule"]] = by_rule.get(issue["rule"], 0) + 1
    return {
        "rows_received": int(len(tape)),
        "loans_after_cleaning": int(len(cleaned)),
        "issues_found": len(issues),
        "issues_by_rule": by_rule,
        "issues": issues,
        "balance_after_cleaning": total,
        "initial_pool_balance_in_deal_terms": expected,
        "reconciles": abs(total - expected) < 0.01,
    }


def load_clean_tape(path=None, supplementary=None):
    """The cleaned cut-off tape, for the other tools (a fresh copy each time)."""
    return _clean_tape_cached(str(path) if path else None, str(supplementary) if supplementary else None).copy()


@lru_cache(maxsize=4)
def _clean_tape_cached(path, supplementary=None):
    tape = read_tape(path, supplementary)
    return clean_tape(tape, find_issues(tape))
