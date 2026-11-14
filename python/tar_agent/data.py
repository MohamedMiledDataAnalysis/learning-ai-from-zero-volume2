"""Where the deal pack lives, and small helpers to read it.

Every tool reads files through this module, so the folder is set in one place.
Set the environment variable TAR_DATA_DIR to use another copy of the data.

The deal pack holds the files the parties really send:

    originator/        Kestrel's pool-cut loan tape (Excel) and its data dictionary (Excel)
    servicer_reports/  Kestrel's monthly servicer report (Excel) and loan-level data file (CSV)
    investor_reports/  Larkmead Bank's monthly investor report (PDF), one per payment date
    loan_level/        the monthly FCA loan-level file (template SECN 12 Annex 5, fields AUTL1 to AUTL84)

The functions below turn each file into a table with short working names (loan_id,
current_balance, ...), so the tools never depend on how one party labels its columns.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(os.environ.get("TAR_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

N_PERIODS = 12

STANDARD_REGIONS = [
    "London", "South East", "South West", "East of England", "East Midlands", "West Midlands",
    "North West", "North East", "Yorkshire and the Humber", "Wales", "Scotland", "Northern Ireland",
]


@lru_cache(maxsize=1)
def deal_terms():
    """The deal terms: notes, fees, reserve fund, trigger limits, definitions."""
    return json.loads((DATA_DIR / "deal_terms.json").read_text(encoding="utf-8"))


def period_stem(period):
    """Period 1 -> '2026_01' (the part of the file names that identifies the month)."""
    check_period(period)
    return f"2026_{period:02d}"


def check_period(period):
    if isinstance(period, bool) or not isinstance(period, int) or not 1 <= period <= N_PERIODS:
        raise ValueError(f"period must be a whole number from 1 to {N_PERIODS}, not {period!r}")


def payment_date(period):
    """Period 1 -> '2026-02-20': the payment date that follows the collection period."""
    check_period(period)
    day = deal_terms()["deal"]["payment_day"]
    year, month = (2026, period + 1) if period < 12 else (2027, 1)
    return f"{year}-{month:02d}-{day:02d}"


def investor_report_path(period):
    return DATA_DIR / "investor_reports" / f"Thames_2026-1_Investor_Report_{payment_date(period)}.pdf"


def investor_report(period):
    """The cash manager's investor report for one period, read from its PDF."""
    from .tools.investor_report import read_investor_report
    return read_investor_report(str(investor_report_path(period)))


# The servicer's column names (Regional tab of the servicer report) and the working names.
REGIONAL_NAMES = {
    "Collection Period": "period", "Region": "region", "Live Agreements": "loans_outstanding",
    "Outstanding Capital Balance": "balance", "Balance 1 Instalment in Arrears": "balance_1_in_arrears",
    "Balance 2 Instalments in Arrears": "balance_2_in_arrears",
    "Balance 3 Instalments in Arrears": "balance_3_in_arrears", "Defaults in Period": "defaults",
    "Early Settlements in Period": "prepayments",
}


def servicer_report_path(period):
    return DATA_DIR / "servicer_reports" / f"Kestrel_Thames_2026-1_Servicer_Report_{period_stem(period).replace('_', '-')}.xlsx"


def servicer_report(period):
    """The regional table of the servicer report: one row per region."""
    table = pd.read_excel(servicer_report_path(period), sheet_name="Regional")
    _check_columns(table, REGIONAL_NAMES, servicer_report_path(period).name)
    table = table.rename(columns=REGIONAL_NAMES)
    money = [c for c in table.columns if c not in ("period", "region", "loans_outstanding")]
    table[money] = table[money].astype(float)
    return table


# The loan-level data file sent with each servicer report.
LOAN_LEVEL_NAMES = {
    "Agreement Number": "loan_id", "Collection Period": "period", "Period End Date": "period_end",
    "Product Type": "product", "New/Used": "vehicle_type", "Fuel Type": "fuel_type",
    "Amount Financed": "original_balance", "Customer Rate %": "interest_rate_pct",
    "Bureau Score at Origination": "credit_score", "Region": "region", "Postcode Area": "postcode_area",
    "Final Instalment Date": "maturity_date", "Opening Capital Balance": "opening_balance",
    "Instalments Paid": "instalments_paid", "Scheduled Capital Received": "principal_paid",
    "Interest Received": "interest_paid", "Early Settlement Amount": "prepayment",
    "Default Balance": "defaulted_balance", "Closing Capital Balance": "closing_balance",
    "Instalments in Arrears": "instalments_in_arrears", "Account Status": "status",
}
# The servicer's words for the status of an agreement, and the working words.
STATUS_NAMES = {"Current": "Current", "Arrears": "Arrears", "Defaulted": "Defaulted", "Settled Early": "Prepaid",
                "Paid Out": "Repaid"}
PERFORMANCE_COLUMNS = ["loan_id", "period", "period_end", "opening_balance", "instalments_paid", "principal_paid",
                       "interest_paid", "prepayment", "defaulted_balance", "closing_balance",
                       "instalments_in_arrears", "status"]
STATIC_COLUMNS = ["loan_id", "product", "vehicle_type", "fuel_type", "original_balance", "interest_rate_pct",
                  "credit_score", "region", "postcode_area", "maturity_date"]


def loan_level_path(period):
    return DATA_DIR / "servicer_reports" / f"Kestrel_Thames_2026-1_Loan_Level_Data_{period_stem(period).replace('_', '-')}.csv"


def loan_level_data(period):
    """The servicer's loan-level data for one period, with working names."""
    table = pd.read_csv(loan_level_path(period), keep_default_na=False, na_values=[])
    _check_columns(table, LOAN_LEVEL_NAMES, loan_level_path(period).name)
    table = table.rename(columns=LOAN_LEVEL_NAMES)
    table["status"] = table.status.map(STATUS_NAMES)
    return table


@lru_cache(maxsize=1)
def _loan_level_all():
    return pd.concat([loan_level_data(t) for t in range(1, N_PERIODS + 1)], ignore_index=True)


def loan_performance():
    """One row per loan and period: the twelve loan-level files put together, sorted by loan, then period."""
    rows = _loan_level_all()[PERFORMANCE_COLUMNS]
    return rows.sort_values(["loan_id", "period"], kind="stable").reset_index(drop=True)


def loan_snapshot():
    """Every loan of the pool at the end of the last period: its fixed fields and its latest status."""
    rows = _loan_level_all()
    last = rows.groupby("loan_id", sort=False).tail(1).set_index("loan_id")
    snap = rows.drop_duplicates("loan_id")[STATIC_COLUMNS].reset_index(drop=True)
    snap["status"] = snap.loan_id.map(last.status)
    snap["current_balance"] = snap.loan_id.map(last.closing_balance)
    snap["instalments_in_arrears"] = snap.loan_id.map(last.instalments_in_arrears)
    snap["status_period"] = snap.loan_id.map(last.period)
    return snap


def fca_loan_level_path(period):
    return DATA_DIR / "loan_level" / f"THAMES_2026-1_AUTL_{_period_end(period)}.csv"


def fca_loan_level(period):
    """The FCA loan-level file for one period, as received: field codes AUTL1 to AUTL84, all values as text
    (the no-data codes ND1 to ND5 are text too)."""
    return pd.read_csv(fca_loan_level_path(period), dtype=str, keep_default_na=False, na_values=[])


def fca_investor_report_path(period):
    return DATA_DIR / "loan_level" / f"THAMES_2026-1_IVS_{_period_end(period)}.xlsx"


def fca_investor_report(period):
    """The FCA investor report for one period (template SECN 12 Annex 12), as received: a dictionary of three
    tables, IVSS (securitisation information), IVSR (tests and triggers) and IVSF (priority of payments)."""
    return pd.read_excel(fca_investor_report_path(period), sheet_name=None, dtype=str, keep_default_na=False)


def servicer_summary(period):
    """The Summary sheet of the servicer report: {line: amount}."""
    table = pd.read_excel(servicer_report_path(period), sheet_name="Summary")
    return dict(zip(table.iloc[:, 0], table.iloc[:, 1]))


def _period_end(period):
    check_period(period)
    import calendar
    return f"2026-{period:02d}-{calendar.monthrange(2026, period)[1]:02d}"


def _check_columns(table, names, file_name):
    missing = [c for c in names if c not in table.columns]
    if missing:
        raise ValueError(f"{file_name}: missing columns {missing}; the file does not follow the expected layout")
