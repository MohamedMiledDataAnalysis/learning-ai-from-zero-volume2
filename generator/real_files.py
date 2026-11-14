"""Write the Thames deal pack in the formats the parties really send.

generate_deal_pack.py simulates the deal: loans, monthly performance, waterfall and
investor reports. This module writes those results the way each party would:

    data/originator/       Kestrel's pool-cut tape in the FCA template (AUTL fields), a supplementary file and
                           the data dictionary (Excel)
    data/servicer_reports/ Kestrel's monthly servicer report (Excel) and loan-level data file (CSV)
    data/investor_reports/ Larkmead Bank's monthly investor report (PDF, and the same figures in Excel)
    data/loan_level/       the monthly FCA files: loan-level data (SECN 12 Annex 5, fields AUTL1 to AUTL84)
                           and investor report (SECN 12 Annex 12, fields IVSS, IVSR and IVSF)

Every file is written from the same numbers, so the agent's readers can turn each one
back into exactly the tables the simulation produced (the tests check this).
"""

import calendar
import csv
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------- parties and identifiers

ISSUER = "Thames Auto Receivables 2026-1 plc"
ORIGINATOR = "Kestrel Motor Finance Ltd"
CASH_MANAGER = "Larkmead Bank plc"
TRUSTEE = "Albion Trustee Services Ltd"
ORIGINATOR_LEI = "00000000KESTREL00001"          # fictional: 20 characters, as an LEI has
ISSUER_LEI = "00000000THAMES2026A1"
UNIQUE_ID = ORIGINATOR_LEI + "N" + "2026" + "01"   # AUTL1: reporting entity LEI + N + year + number
ISINS = {"A": "XS0000000001", "B": "XS0000000002", "C": "XS0000000003", "D": "XS0000000004"}
SIGNATORY = ("Claire Holloway", "Head of Securitisation and Funding")
CONTACT = "thames2026-1@larkmead.example"

# NUTS 2016 level-3 region of each postcode area (field AUTL10).
NUTS3 = {
    "E": "UKI42", "N": "UKI43", "SE": "UKI44", "SW": "UKI34", "W": "UKI33",
    "GU": "UKJ25", "RG": "UKJ11", "BN": "UKJ21", "ME": "UKJ41", "OX": "UKJ14",
    "BS": "UKK11", "EX": "UKK43", "PL": "UKK41", "BA": "UKK12",
    "CB": "UKH12", "NR": "UKH15", "CO": "UKH34", "IP": "UKH14",
    "NG": "UKF14", "LE": "UKF21", "DE": "UKF11",
    "B": "UKG31", "CV": "UKG33", "WV": "UKG39", "ST": "UKG23",
    "M": "UKD33", "L": "UKD72", "PR": "UKD45", "BL": "UKD36", "WA": "UKD61",
    "NE": "UKC22", "SR": "UKC23", "DH": "UKC14",
    "LS": "UKE42", "S": "UKE32", "BD": "UKE41", "HU": "UKE11",
    "CF": "UKL22", "SA": "UKL18", "LL": "UKL13",
    "G": "UKM82", "EH": "UKM75", "AB": "UKM50", "DD": "UKM71",
    "BT": "UKN06",
}

# ---------------------------------------------------------------- the originator's own field names

# Monthly loan-level data file sent with the servicer report.
LOAN_LEVEL_FIELDS = [
    ("Agreement Number", "loan_id", "Kestrel's unique reference for the finance agreement."),
    ("Collection Period", "period", "Number of the monthly collection period (1 = January 2026)."),
    ("Period End Date", "period_end", "Last day of the collection period (YYYY-MM-DD)."),
    ("Product Type", "product", "HP or PCP."),
    ("New/Used", "vehicle_type", "New or Used."),
    ("Fuel Type", "fuel_type", "Petrol, Diesel, Hybrid or Electric."),
    ("Amount Financed", "original_balance", "Amount lent at the start of the agreement (£)."),
    ("Customer Rate %", "interest_rate_pct", "Annual interest rate charged to the customer, in per cent."),
    ("Bureau Score at Origination", "credit_score", "Credit reference agency score at application."),
    ("Region", "region", "ONS standard region of the customer's address."),
    ("Postcode Area", "postcode_area", "Letters of the customer's postcode before the first digit."),
    ("Final Instalment Date", "maturity_date", "Date of the last scheduled payment (YYYY-MM-DD)."),
    ("Opening Capital Balance", "opening_balance", "Capital owed at the start of the period (£)."),
    ("Instalments Paid", "instalments_paid", "Number of instalments received in the period (0, 1 or more)."),
    ("Scheduled Capital Received", "principal_paid", "Capital part of the instalments received (£)."),
    ("Interest Received", "interest_paid", "Interest part of the instalments received (£)."),
    ("Early Settlement Amount", "prepayment", "Capital repaid early when the customer settled the agreement (£)."),
    ("Default Balance", "defaulted_balance", "Capital written off as defaulted in the period (£)."),
    ("Closing Capital Balance", "closing_balance", "Capital owed at the end of the period (£)."),
    ("Instalments in Arrears", "instalments_in_arrears", "Number of unpaid instalments at the end of the period "
     "(4 means the agreement has defaulted)."),
    ("Account Status", "status", "Current, Arrears, Defaulted, Settled Early or Paid Out."),
]
STATUS_WORDS = {"Current": "Current", "Arrears": "Arrears", "Defaulted": "Defaulted",
                "Prepaid": "Settled Early", "Repaid": "Paid Out"}

# Regional tab of the servicer report.
REGIONAL_FIELDS = [
    ("Collection Period", "period"), ("Region", "region"), ("Live Agreements", "loans_outstanding"),
    ("Outstanding Capital Balance", "balance"), ("Balance 1 Instalment in Arrears", "balance_1_in_arrears"),
    ("Balance 2 Instalments in Arrears", "balance_2_in_arrears"),
    ("Balance 3 Instalments in Arrears", "balance_3_in_arrears"), ("Defaults in Period", "defaults"),
    ("Early Settlements in Period", "prepayments"),
]

# The no-data codes of the FCA templates (SECN 11.3 and Article 9 of the transparency rules).
ND_CODES = [
    ("ND1", "Data not collected because it was not required by the lending or underwriting criteria at the time "
            "of origination."),
    ("ND2", "Data collected at application but not loaded into the reporting system at origination."),
    ("ND3", "Data collected at application but loaded into a system separate from the reporting system."),
    ("ND4", "Data collected but available only from a later date, which must be given with the code (ND4-YYYY-MM-DD)."),
    ("ND5", "Not applicable: the field is not relevant to this exposure."),
]

# SECN 12 Annex 5 (automobile underlying exposures): code, name, format, ND1-ND4 allowed, ND5 allowed.
AUTL = [
    ("AUTL1", "Unique Identifier", "{ALPHANUM-28}", "NO", "NO"),
    ("AUTL2", "Original Underlying Exposure Identifier", "{ALPHANUM-1000}", "NO", "NO"),
    ("AUTL3", "New Underlying Exposure Identifier", "{ALPHANUM-1000}", "NO", "NO"),
    ("AUTL4", "Original Obligor Identifier", "{ALPHANUM-1000}", "NO", "NO"),
    ("AUTL5", "New Obligor Identifier", "{ALPHANUM-1000}", "NO", "NO"),
    ("AUTL6", "Data Cut-Off Date", "{DATEFORMAT}", "NO", "NO"),
    ("AUTL7", "Pool Addition Date", "{DATEFORMAT}", "NO", "YES"),
    ("AUTL8", "Date Of Repurchase", "{DATEFORMAT}", "NO", "YES"),
    ("AUTL9", "Redemption Date", "{DATEFORMAT}", "NO", "YES"),
    ("AUTL10", "Geographic Region - Obligor", "{NUTS}", "YES", "NO"),
    ("AUTL11", "Geographic Region Classification", "{YEAR}", "YES", "NO"),
    ("AUTL12", "Employment Status", "{LIST}", "YES", "NO"),
    ("AUTL13", "Credit Impaired Obligor", "{Y/N}", "NO", "YES"),
    ("AUTL14", "Obligor Legal Type", "{LIST}", "YES", "NO"),
    ("AUTL15", "Customer Type", "{LIST}", "YES", "NO"),
    ("AUTL16", "Primary Income", "{MONETARY}", "YES", "YES"),
    ("AUTL17", "Primary Income Type", "{LIST}", "YES", "NO"),
    ("AUTL18", "Primary Income Currency", "{CURRENCYCODE_3}", "YES", "YES"),
    ("AUTL19", "Primary Income Verification", "{LIST}", "YES", "NO"),
    ("AUTL20", "Revenue", "{MONETARY}", "YES", "YES"),
    ("AUTL21", "Financial Statement Currency", "{CURRENCYCODE_3}", "YES", "YES"),
    ("AUTL22", "Special Scheme", "{ALPHANUM-10000}", "YES", "YES"),
    ("AUTL23", "Product Type", "{LIST}", "NO", "YES"),
    ("AUTL24", "Origination Date", "{DATEFORMAT}", "YES", "NO"),
    ("AUTL25", "Maturity Date", "{DATEFORMAT}", "NO", "YES"),
    ("AUTL26", "Original Term", "{INTEGER-9999}", "YES", "YES"),
    ("AUTL27", "Origination Channel", "{LIST}", "YES", "YES"),
    ("AUTL28", "Currency Denomination", "{CURRENCYCODE_3}", "NO", "NO"),
    ("AUTL29", "Original Principal Balance", "{MONETARY}", "YES", "YES"),
    ("AUTL30", "Current Principal Balance", "{MONETARY}", "NO", "YES"),
    ("AUTL31", "Purchase Price", "{PERCENTAGE}", "NO", "YES"),
    ("AUTL32", "Amortisation Type", "{LIST}", "YES", "NO"),
    ("AUTL33", "Principal Grace Period End Date", "{DATEFORMAT}", "NO", "YES"),
    ("AUTL34", "Scheduled Principal Payment Frequency", "{LIST}", "NO", "YES"),
    ("AUTL35", "Scheduled Interest Payment Frequency", "{LIST}", "NO", "YES"),
    ("AUTL36", "Payment Method", "{LIST}", "YES", "NO"),
    ("AUTL37", "Payment Due", "{MONETARY}", "NO", "YES"),
    ("AUTL38", "Balloon Amount", "{MONETARY}", "YES", "YES"),
    ("AUTL39", "Down Payment Amount", "{MONETARY}", "YES", "YES"),
    ("AUTL40", "Current Interest Rate", "{PERCENTAGE}", "NO", "YES"),
    ("AUTL41", "Current Interest Rate Index", "{LIST}", "NO", "YES"),
    ("AUTL42", "Current Interest Rate Index Tenor", "{LIST}", "NO", "YES"),
    ("AUTL43", "Current Interest Rate Margin", "{PERCENTAGE}", "NO", "YES"),
    ("AUTL44", "Interest Rate Reset Interval", "{INTEGER-9999}", "NO", "YES"),
    ("AUTL45", "Interest Rate Cap", "{PERCENTAGE}", "NO", "YES"),
    ("AUTL46", "Interest Rate Floor", "{PERCENTAGE}", "NO", "YES"),
    ("AUTL47", "Number Of Payments Before Securitisation", "{INTEGER-9999}", "YES", "NO"),
    ("AUTL48", "Percentage Of Prepayments Allowed Per Year", "{PERCENTAGE}", "YES", "YES"),
    ("AUTL49", "Prepayment Fee", "{MONETARY}", "NO", "YES"),
    ("AUTL50", "Prepayment Fee End Date", "{DATEFORMAT}", "YES", "YES"),
    ("AUTL51", "Prepayment Date", "{DATEFORMAT}", "YES", "YES"),
    ("AUTL52", "Cumulative Prepayments", "{MONETARY}", "YES", "YES"),
    ("AUTL53", "Manufacturer", "{ALPHANUM-100}", "YES", "NO"),
    ("AUTL54", "Model", "{ALPHANUM-100}", "YES", "NO"),
    ("AUTL55", "Year Of Registration", "{YEAR}", "YES", "YES"),
    ("AUTL56", "New Or Used", "{LIST}", "YES", "NO"),
    ("AUTL57", "Energy Performance Certificate Value", "{LIST}", "YES", "YES"),
    ("AUTL58", "Energy Performance Certificate Provider Name", "{ALPHANUM-100}", "YES", "YES"),
    ("AUTL59", "Original Loan-To-Value", "{PERCENTAGE}", "YES", "NO"),
    ("AUTL60", "Original Valuation Amount", "{MONETARY}", "YES", "NO"),
    ("AUTL61", "Original Residual Value Of Vehicle", "{MONETARY}", "YES", "YES"),
    ("AUTL62", "Option To Buy Price", "{MONETARY}", "NO", "YES"),
    ("AUTL63", "Securitised Residual Value", "{MONETARY}", "NO", "YES"),
    ("AUTL64", "Updated Residual Value Of Vehicle", "{MONETARY}", "NO", "YES"),
    ("AUTL65", "Date Of Updated Residual Valuation Of Vehicle", "{DATEFORMAT}", "NO", "YES"),
    ("AUTL66", "Date Of Restructuring", "{DATEFORMAT}", "YES", "YES"),
    ("AUTL67", "Date Last In Arrears", "{DATEFORMAT}", "YES", "YES"),
    ("AUTL68", "Arrears Balance", "{MONETARY}", "NO", "NO"),
    ("AUTL69", "Number Of Days In Arrears", "{INTEGER-9999}", "NO", "NO"),
    ("AUTL70", "Account Status", "{LIST}", "NO", "NO"),
    ("AUTL71", "Reason for Default or Foreclosure", "{LIST}", "YES", "YES"),
    ("AUTL72", "Default Amount", "{MONETARY}", "NO", "YES"),
    ("AUTL73", "Default Date", "{DATEFORMAT}", "NO", "YES"),
    ("AUTL74", "Allocated Losses", "{MONETARY}", "NO", "YES"),
    ("AUTL75", "Residual Value Losses", "{MONETARY}", "YES", "YES"),
    ("AUTL76", "Cumulative Recoveries", "{MONETARY}", "NO", "YES"),
    ("AUTL77", "Sale Price", "{MONETARY}", "NO", "YES"),
    ("AUTL78", "Deposit Amount", "{MONETARY}", "NO", "YES"),
    ("AUTL79", "Original Lender Name", "{ALPHANUM-100}", "YES", "YES"),
    ("AUTL80", "Original Lender Legal Entity Identifier", "{LEI}", "YES", "YES"),
    ("AUTL81", "Original Lender Establishment Country", "{COUNTRYCODE_2}", "YES", "YES"),
    ("AUTL82", "Originator Name", "{ALPHANUM-100}", "NO", "NO"),
    ("AUTL83", "Originator Legal Entity Identifier", "{LEI}", "NO", "NO"),
    ("AUTL84", "Originator Establishment Country", "{COUNTRYCODE_2}", "NO", "NO"),
]
assert [c for c, *_ in AUTL] == [f"AUTL{i}" for i in range(1, 85)]

EMPLOYMENT_CODE = {"Employed": "EMUK", "Self-employed": "SFEM", "Retired": "PNNR", "Other": "OTHR"}
PRODUCT_CODE = {"HP": "HIRP", "PCP": "PPUR"}
NEW_USED_CODE = {"New": "NEWX", "Used": "USED"}
STATUS_CODE = {"Current": "PERF", "Arrears": "ARRE", "Defaulted": "DFLT", "Prepaid": "RDMD", "Repaid": "RDMD"}

# ---------------------------------------------------------------- Excel styling

NAVY, GOLD, GREY = "1F2A44", "B08D57", "F2F2F2"
THIN = Side(style="thin", color="BFBFBF")


def _title_rows(ws, lines):
    for i, (text, bold) in enumerate(lines, start=1):
        ws.cell(row=i, column=1, value=text).font = Font(name="Arial", size=12 if i == 1 else 10, bold=bold,
                                                          color=NAVY)


def _header(ws, row, names, widths=None):
    for j, name in enumerate(names, start=1):
        c = ws.cell(row=row, column=j, value=name)
        c.font = Font(name="Arial", size=9, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=NAVY)
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        c.border = Border(bottom=THIN)
        ws.column_dimensions[get_column_letter(j)].width = (widths or {}).get(j, max(12, min(len(name) + 2, 24)))
    ws.row_dimensions[row].height = 30


def _body_font(ws, first_row, last_row, ncol):
    for row in ws.iter_rows(min_row=first_row, max_row=last_row, max_col=ncol):
        for c in row:
            c.font = Font(name="Arial", size=9)


def _save(wb, path):
    """Save so that the same seed gives the same bytes: a fixed creation date in the workbook, and a fixed date on
    every member of the zip archive that an .xlsx file is (openpyxl stamps both with the current time)."""
    import io
    import re
    import zipfile
    wb.properties.creator = ORIGINATOR
    wb.properties.created = wb.properties.modified = datetime(2026, 1, 1)
    buffer = io.BytesIO()
    wb.save(buffer)
    with zipfile.ZipFile(buffer) as src, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)", rb"\g<1>2026-01-01T00:00:00Z\g<2>",
                              data)
            info = zipfile.ZipInfo(item.filename, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(info, data)


def _iso(d):
    return date.fromisoformat(str(d))


# ---------------------------------------------------------------- 1. pool-cut tape and data dictionary

# The fields the FCA template does not have, sent by Kestrel in a supplementary file joined on AUTL2.
SUPPLEMENTARY_FIELDS = [
    ("AUTL2", "loan_id", "Original Underlying Exposure Identifier: the agreement number, the key that joins this "
                         "file to the FCA template file.", "Text", "TAR + 5 digits"),
    ("Bureau Score at Origination", "credit_score", "Credit reference agency score at application.", "Integer",
     "0 to 999"),
    ("Fuel Type", "fuel_type", "Fuel or power source of the vehicle.", "Text", "Petrol; Diesel; Hybrid; Electric"),
    ("Region", "region", "ONS standard region of the customer's address.", "Text",
     "One of the 12 ONS regions of the United Kingdom"),
    ("Postcode Area", "postcode_area", "Letters of the customer's postcode before the first digit.", "Text",
     "A valid UK postcode area"),
]

# List codes used in the pool cut, with Kestrel's own value for each (sheet "List Codes" of the dictionary).
LIST_CODES = ([("AUTL23", PRODUCT_CODE[k], v, k) for k, v in [("HP", "Hire Purchase"), ("PCP", "(Personal) Contract Purchase")]]
              + [("AUTL56", NEW_USED_CODE[k], k, k) for k in ["New", "Used"]]
              + [("AUTL12", EMPLOYMENT_CODE[k], v, k) for k, v in
                 [("Employed", "Employed - Sector Unknown"), ("Self-employed", "Self-employed"),
                  ("Retired", "Pensioner"), ("Other", "Other")]]
              + [("AUTL70", "PERF", "Performing", "Current"), ("AUTL70", "ARRE", "Arrears", "Arrears"),
                 ("AUTL70", "DFLT", "Defaulted", "Defaulted"), ("AUTL70", "RDMD", "Redeemed", "Settled Early or Paid Out")])


def pool_cut_rows(tape, cut_off, closing_date):
    """The pool-cut tape in the FCA template: one row per row received (duplicates included)."""
    rows = []
    for r in tape.to_dict("records"):
        rec = dict.fromkeys([c for c, *_ in AUTL], "ND5")
        rec.update({
            "AUTL1": UNIQUE_ID, "AUTL2": r["loan_id"], "AUTL3": r["loan_id"], "AUTL4": "OB" + r["loan_id"][3:],
            "AUTL5": "OB" + r["loan_id"][3:], "AUTL6": cut_off.isoformat(), "AUTL7": closing_date,
            "AUTL10": NUTS3[r["postcode_area"]] if r["postcode_area"] else "ND2", "AUTL11": "2016",
            "AUTL12": EMPLOYMENT_CODE[r["employment_status"]], "AUTL13": "N", "AUTL14": "INDV", "AUTL15": "CNRO",
            "AUTL16": f"{r['annual_income']:.2f}", "AUTL17": "OTHR", "AUTL18": "GBP", "AUTL19": "SCRG",
            "AUTL23": PRODUCT_CODE[r["product"]], "AUTL24": str(r["origination_date"]),
            "AUTL25": str(r["maturity_date"]), "AUTL26": str(int(r["original_term_months"])), "AUTL27": "ADLR",
            "AUTL28": "GBP", "AUTL29": f"{r['original_balance']:.2f}", "AUTL30": f"{r['current_balance']:.2f}",
            "AUTL31": "100.0000", "AUTL32": "OTHR" if r["product"] == "PCP" else "FRXX", "AUTL34": "MNTH",
            "AUTL35": "MNTH", "AUTL36": "CDTX", "AUTL37": f"{r['monthly_instalment']:.2f}",
            "AUTL38": f"{r['balloon_amount']:.2f}", "AUTL39": f"{r['vehicle_value'] - r['original_balance']:.2f}",
            "AUTL40": f"{r['interest_rate_pct']:.4f}",
            "AUTL47": str(int(r["original_term_months"] - r["remaining_term_months"])), "AUTL49": "0.00",
            "AUTL52": "0.00", "AUTL53": "ND2", "AUTL54": "ND2", "AUTL55": "ND2",
            "AUTL56": NEW_USED_CODE[r["vehicle_type"]], "AUTL59": f"{r['ltv_original_pct']:.4f}",
            "AUTL60": f"{r['vehicle_value']:.2f}",
            **({"AUTL61": f"{r['balloon_amount']:.2f}", "AUTL62": f"{r['balloon_amount']:.2f}",
                "AUTL63": f"{r['balloon_amount']:.2f}"} if r["product"] == "PCP" else {}),
            "AUTL68": "0.00", "AUTL69": str(int(r["days_past_due"])), "AUTL70": "PERF", "AUTL72": "0.00",
            "AUTL78": "0.00", "AUTL79": ORIGINATOR, "AUTL80": ORIGINATOR_LEI, "AUTL81": "GB", "AUTL82": ORIGINATOR,
            "AUTL83": ORIGINATOR_LEI, "AUTL84": "GB",
        })
        rows.append(rec)
    return rows


def write_pool_cut_autl(tape, cut_off, closing_date, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[c for c, *_ in AUTL], lineterminator="\n")
        w.writeheader()
        w.writerows(pool_cut_rows(tape, cut_off, closing_date))


def write_supplementary(tape, path):
    """One row per agreement (no duplicate): the fields the FCA template does not have."""
    rows = tape.drop_duplicates("loan_id")[[c for _, c, *_ in SUPPLEMENTARY_FIELDS]].copy()
    rows.columns = [n for n, *_ in SUPPLEMENTARY_FIELDS]
    rows.to_csv(path, index=False, lineterminator="\n")


def write_data_dictionary(path, cut_off):
    wb = Workbook()
    ws = wb.active
    ws.title = "Read Me"
    _title_rows(ws, [(f"{ORIGINATOR} — {ISSUER}", True), ("Data dictionary, version 1.2", False),
                     (f"Applies to the pool-cut tape as at {cut_off.isoformat()}, the monthly loan-level data "
                      "file and the monthly servicer report.", False)])
    notes = [
        "The pool-cut tape follows the FCA template for automobile underlying exposures (SECN 12 Annex 5): file "
        "THAMES_2026-1_AUTL_Pool_Cut_2025-12-31.csv, one row per agreement, fields AUTL1 to AUTL84.",
        "Sheet 'FCA Template AUTL': every field of the template, whether ND codes are allowed, and how Kestrel "
        "fills it.",
        "Sheet 'Supplementary Data': the fields the template does not have (credit score, fuel type, region, "
        "postcode area), in file Kestrel_Thames_2026-1_Supplementary_Data_2025-12-31.csv, joined on AUTL2.",
        "Sheet 'List Codes': the template's codes used by Kestrel, with Kestrel's own value for each.",
        "Sheet 'Loan-Level Data': fields of the monthly loan-level data file sent with each servicer report.",
        "Sheet 'Servicer Report': definition of each line of the monthly servicer report.",
        "Sheet 'FCA Template AUTL': the fields of the FCA template for automobile underlying exposures "
        "(SECN 12 Annex 5), used for the monthly loan-level disclosure, with the no-data rules of SECN 11 Annex 5.",
        "Sheet 'FCA Template IVS': the fields of the FCA investor report template (SECN 12 Annex 12), used for the "
        "monthly investor report file next to the loan-level file.",
        "Sheet 'No-Data Codes': the meaning of the codes ND1 to ND5.",
        "Amounts are in pounds sterling. Dates in the Excel files are Excel dates shown as DD/MM/YYYY; "
        "dates in CSV files are written YYYY-MM-DD.",
        "Questions on this dictionary: Securitisation Reporting, Kestrel Motor Finance Ltd, Leicester.",
    ]
    for i, n in enumerate(notes, start=5):
        ws.cell(row=i, column=1, value=n).font = Font(name="Arial", size=10)
    ws.column_dimensions["A"].width = 140

    ws = wb.create_sheet("Supplementary Data")
    _header(ws, 1, ["Field Name", "Description", "Data Type", "Allowed Values"], {1: 30, 2: 80, 3: 11, 4: 46})
    for i, (name, _col, desc, typ, allowed) in enumerate(SUPPLEMENTARY_FIELDS, start=2):
        for j, v in enumerate([name, desc, typ, allowed], start=1):
            ws.cell(row=i, column=j, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    _body_font(ws, 2, len(SUPPLEMENTARY_FIELDS) + 1, 4)

    ws = wb.create_sheet("List Codes")
    _header(ws, 1, ["Field Code", "Code", "Meaning (FCA template)", "Kestrel Value"], {1: 11, 2: 8, 3: 40, 4: 28})
    for i, row in enumerate(LIST_CODES, start=2):
        for j, v in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=v)
    _body_font(ws, 2, len(LIST_CODES) + 1, 4)

    ws = wb.create_sheet("Loan-Level Data")
    _header(ws, 1, ["Field No", "Field Name", "Description"], {1: 9, 2: 30, 3: 90})
    for i, (name, _col, desc) in enumerate(LOAN_LEVEL_FIELDS, start=1):
        for j, v in enumerate([i, name, desc], start=1):
            ws.cell(row=i + 1, column=j, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    _body_font(ws, 2, len(LOAN_LEVEL_FIELDS) + 1, 3)

    ws = wb.create_sheet("Servicer Report")
    _header(ws, 1, ["Sheet", "Line", "Definition"], {1: 14, 2: 36, 3: 90})
    lines = [
        ("Summary", "Opening Capital Balance", "Capital owed on the live agreements at the start of the period."),
        ("Summary", "Scheduled Capital Received", "Capital part of the instalments received in the period."),
        ("Summary", "Early Settlements", "Capital repaid when customers settled their agreements early."),
        ("Summary", "Defaults", "Capital of the agreements that defaulted in the period (4 unpaid instalments)."),
        ("Summary", "Closing Capital Balance", "Opening balance less capital received, early settlements and "
                                               "defaults."),
        ("Summary", "Interest Received", "Interest part of the instalments received in the period."),
        ("Summary", "Recoveries", "Amounts recovered in the period on agreements that defaulted earlier, net of "
                                  "costs."),
        ("Arrears", "Instalments in Arrears", "Number of contractual instalments due and unpaid at the end of the "
                                              "period: 0, 1, 2 or 3. Days past due are 30 per unpaid instalment, so 3 "
                                              "instalments are 90 days or more (the 90+ day arrears of the "
                                              "Prospectus)."),
        ("Regional", "Live Agreements", "Agreements that are Current or in Arrears at the end of the period."),
        ("Regional", "Balance n Instalments in Arrears", "Closing capital balance of the live agreements with n "
                                                         "unpaid instalments."),
        ("Defaults", "Default Balance", "Capital owed when the agreement defaulted."),
    ]
    for i, row in enumerate(lines, start=2):
        for j, v in enumerate(row, start=1):
            ws.cell(row=i, column=j, value=v).alignment = Alignment(wrap_text=True, vertical="top")
    _body_font(ws, 2, len(lines) + 1, 3)

    ws = wb.create_sheet("FCA Template AUTL")
    _header(ws, 1, ["Field Code", "Field Name", "Format", "ND1-ND4 Allowed?", "ND5 Allowed?",
                    "Kestrel Source"], {1: 11, 2: 46, 3: 18, 4: 14, 5: 12, 6: 50})
    source = {"AUTL2": "Agreement number", "AUTL6": "Cut-off date of the tape", "AUTL10": "NUTS3 region of the "
              "customer's postcode area; ND2 where the postcode is missing", "AUTL12": "Employment status declared "
              "at application", "AUTL16": "Gross annual income declared at application", "AUTL23": "HP -> HIRP, "
              "PCP -> PPUR", "AUTL24": "Agreement start date", "AUTL25": "Final instalment date", "AUTL26":
              "Number of monthly instalments", "AUTL29": "Amount financed", "AUTL30": "Outstanding capital "
              "balance, including any final payment", "AUTL37": "Monthly instalment", "AUTL38": "Optional final "
              "payment (PCP); 0 for HP", "AUTL40": "Customer rate, per cent", "AUTL47": "Instalments paid before "
              "the cut-off date", "AUTL53": "ND2: held in the dealer system, not in the reporting system",
              "AUTL56": "New -> NEWX, Used -> USED", "AUTL59": "Amount financed / cash price, per cent", "AUTL60":
              "Cash price of the vehicle", "AUTL69": "30 days per unpaid instalment", "AUTL70": "PERF, ARRE, "
              "DFLT or RDMD"}
    for i, (code, name, fmt, nd14, nd5) in enumerate(AUTL, start=2):
        for j, v in enumerate([code, name, fmt, nd14, nd5, source.get(code, "")], start=1):
            ws.cell(row=i, column=j, value=v)
    _body_font(ws, 2, len(AUTL) + 1, 6)

    ws = wb.create_sheet("FCA Template IVS")
    _header(ws, 1, ["Field Code", "Field Name", "Format", "Section"], {1: 11, 2: 56, 3: 18, 4: 40})
    sections = {"IVSS": "Securitisation information", "IVSR": "Tests, events and triggers",
                "IVSF": "Cash-flow information (priority of payments)"}
    for i, (code, name, fmt) in enumerate(IVSS + IVSR + IVSF, start=2):
        for j, v in enumerate([code, name, fmt, sections[code[:4]]], start=1):
            ws.cell(row=i, column=j, value=v)
    _body_font(ws, 2, len(IVSS + IVSR + IVSF) + 1, 4)

    ws = wb.create_sheet("No-Data Codes")
    _header(ws, 1, ["Code", "Meaning"], {1: 8, 2: 110})
    for i, (code, text) in enumerate(ND_CODES, start=2):
        ws.cell(row=i, column=1, value=code)
        ws.cell(row=i, column=2, value=text).alignment = Alignment(wrap_text=True)
    _body_font(ws, 2, len(ND_CODES) + 1, 2)
    _save(wb, path)


# ---------------------------------------------------------------- 2. servicer report and loan-level data

def loan_level_rows(perf, loans, t):
    static = loans[["loan_id", "product", "vehicle_type", "fuel_type", "original_balance", "interest_rate_pct",
                    "credit_score", "region", "postcode_area", "maturity_date"]].copy()
    static["maturity_date"] = static.maturity_date.astype(str)
    p = perf[perf.period == t].merge(static, on="loan_id", how="left")
    return p[[c for _, c, _ in LOAN_LEVEL_FIELDS]]


def write_loan_level_csv(perf, loans, t, path):
    rows = loan_level_rows(perf, loans, t).copy()
    rows["status"] = rows.status.map(STATUS_WORDS)
    rows.columns = [n for n, _, _ in LOAN_LEVEL_FIELDS]
    rows.to_csv(path, index=False, lineterminator="\n")


def write_servicer_workbook(rep, regional, defaults_rows, t, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Cover"
    end = _iso(rep["collection_period_end"])
    start = end.replace(day=1)
    _title_rows(ws, [(f"{ORIGINATOR}", True), (f"Monthly Servicer Report — {ISSUER}", True),
                     (f"Collection period {t}: {start.strftime('%d/%m/%Y')} to {end.strftime('%d/%m/%Y')}", False)])
    rows = [("Issuer", ISSUER), ("Servicer", ORIGINATOR), ("Cash Manager", CASH_MANAGER),
            ("Collection Period", t), ("Collection Period Start", start.isoformat()),
            ("Collection Period End", end.isoformat()), ("Payment Date", rep["payment_date"]),
            ("Report Date", _business_day_after(end, 5).isoformat())]
    for i, (k, v) in enumerate(rows, start=5):
        ws.cell(row=i, column=1, value=k).font = Font(name="Arial", size=10, bold=True)
        ws.cell(row=i, column=2, value=v).font = Font(name="Arial", size=10)
    cert = (f"The Servicer certifies that, to the best of its knowledge, the information in this report is true "
            f"and accurate and has been prepared in accordance with the Servicing Agreement. Signed for and on "
            f"behalf of {ORIGINATOR}: {SIGNATORY[0]}, {SIGNATORY[1]}.")
    ws.cell(row=14, column=1, value="Servicer Certificate").font = Font(name="Arial", size=10, bold=True)
    ws.cell(row=15, column=1, value=cert).alignment = Alignment(wrap_text=True)
    ws.merge_cells("A15:F18")
    ws.column_dimensions["A"].width, ws.column_dimensions["B"].width = 26, 30

    p = rep["pool"]
    ws = wb.create_sheet("Summary")
    _header(ws, 1, ["Line", "Amount (£)"], {1: 40, 2: 18})
    lines = [("Opening Capital Balance", p["opening_balance"]), ("Scheduled Capital Received", p["principal_received"]),
             ("Early Settlements", p["prepayments"]), ("Defaults", p["defaults"]),
             ("Closing Capital Balance", p["closing_balance"]), ("Interest Received", p["interest_collections"]),
             ("Recoveries", p["recoveries"]), ("Cumulative Defaults", p["cumulative_defaults"]),
             ("Cumulative Recoveries", p["cumulative_recoveries"]), ("Live Agreements", p["loans_outstanding"])]
    for i, (k, v) in enumerate(lines, start=2):
        ws.cell(row=i, column=1, value=k)
        c = ws.cell(row=i, column=2, value=v)
        c.number_format = "#,##0" if k == "Live Agreements" else "#,##0.00"
    _body_font(ws, 2, len(lines) + 1, 2)

    ws = wb.create_sheet("Arrears")
    _header(ws, 1, ["Instalments in Arrears", "Days Past Due", "Number of Agreements", "Capital Balance (£)"],
            {1: 22, 2: 16, 3: 20, 4: 20})
    dpd = ["0", "30-59", "60-89", "90+"]
    for k in range(4):
        b = rep["arrears"][f"{k}_instalments"]
        for j, v in enumerate([k, dpd[k], b["count"], b["balance"]], start=1):
            c = ws.cell(row=k + 2, column=j, value=v)
            if j == 4:
                c.number_format = "#,##0.00"
    _body_font(ws, 2, 5, 4)

    ws = wb.create_sheet("Regional")
    _header(ws, 1, [n for n, _ in REGIONAL_FIELDS])
    for i, rec in enumerate(regional.to_dict("records"), start=2):
        for j, (_, col) in enumerate(REGIONAL_FIELDS, start=1):
            v = rec[col]
            c = ws.cell(row=i, column=j, value=v.item() if hasattr(v, "item") else v)
            if j >= 4:
                c.number_format = "#,##0.00"
    _body_font(ws, 2, len(regional) + 1, len(REGIONAL_FIELDS))

    ws = wb.create_sheet("Defaults")
    _header(ws, 1, ["Agreement Number", "Region", "Product Type", "Default Balance (£)"], {1: 18, 2: 24, 3: 14, 4: 20})
    for i, (lid, region, product, bal) in enumerate(defaults_rows, start=2):
        for j, v in enumerate([lid, region, product, bal], start=1):
            c = ws.cell(row=i, column=j, value=v)
            if j == 4:
                c.number_format = "#,##0.00"
    _body_font(ws, 2, len(defaults_rows) + 1, 4)
    _save(wb, path)


def _business_day_after(d, n):
    from datetime import timedelta
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


# ---------------------------------------------------------------- 3. FCA loan-level file (SECN 12 Annex 5)

def write_autl(perf, loans, recoveries_by_loan, t, closing_date, path):
    end = perf.loc[perf.period == t, "period_end"].iloc[0]
    p = perf[perf.period <= t]
    last = p.groupby("loan_id").tail(1).set_index("loan_id")
    cum_prepay = p.groupby("loan_id").prepayment.sum()
    default_period = p[p.defaulted_balance > 0].set_index("loan_id")
    arrears_dates = p[p.instalments_in_arrears > 0].groupby("loan_id").period_end.max()
    rows = []
    for loan in loans.itertuples():
        lid = loan.loan_id
        if lid not in last.index:
            continue
        s = last.loc[lid]
        if s.status in ("Prepaid", "Repaid") and s.period < t:
            continue                                      # redeemed in an earlier period: no longer reported
        status = s.status if s.period == t else s.status
        arrears = int(s.instalments_in_arrears) if status in ("Current", "Arrears") else 0
        defaulted = lid in default_period.index
        rec = dict.fromkeys([c for c, *_ in AUTL], "ND5")
        rec.update({
            "AUTL1": UNIQUE_ID, "AUTL2": lid, "AUTL3": lid, "AUTL4": "OB" + lid[3:], "AUTL5": "OB" + lid[3:],
            "AUTL6": end, "AUTL7": closing_date,
            "AUTL9": s.period_end if status in ("Prepaid", "Repaid") else "ND5",
            "AUTL10": NUTS3[loan.postcode_area], "AUTL11": "2016",
            "AUTL12": EMPLOYMENT_CODE[loan.employment_status], "AUTL13": "N", "AUTL14": "INDV", "AUTL15": "CNRO",
            "AUTL16": f"{loan.annual_income:.2f}", "AUTL17": "OTHR", "AUTL18": "GBP", "AUTL19": "SCRG",
            "AUTL20": "ND5", "AUTL21": "ND5", "AUTL22": "ND5",
            "AUTL23": PRODUCT_CODE[loan.product], "AUTL24": str(loan.origination_date),
            "AUTL25": str(loan.maturity_date), "AUTL26": str(int(loan.original_term_months)), "AUTL27": "ADLR",
            "AUTL28": "GBP", "AUTL29": f"{loan.original_balance:.2f}",
            "AUTL30": f"{s.closing_balance:.2f}", "AUTL31": "100.0000",
            "AUTL32": "OTHR" if loan.product == "PCP" else "FRXX", "AUTL34": "MNTH", "AUTL35": "MNTH",
            "AUTL36": "CDTX", "AUTL37": f"{loan.monthly_instalment:.2f}", "AUTL38": f"{loan.balloon_amount:.2f}",
            "AUTL39": f"{loan.vehicle_value - loan.original_balance:.2f}",
            "AUTL40": f"{loan.interest_rate_pct:.4f}", "AUTL41": "ND5", "AUTL42": "ND5", "AUTL43": "ND5",
            "AUTL47": str(int(loan.seasoning_months)), "AUTL48": "ND5", "AUTL49": "0.00",
            "AUTL51": s.period_end if status == "Prepaid" else "ND5",
            "AUTL52": f"{cum_prepay.get(lid, 0.0):.2f}", "AUTL53": "ND2", "AUTL54": "ND2", "AUTL55": "ND2",
            "AUTL56": NEW_USED_CODE[loan.vehicle_type], "AUTL57": "ND5", "AUTL58": "ND5",
            "AUTL59": f"{loan.ltv_original_pct:.4f}", "AUTL60": f"{loan.vehicle_value:.2f}",
            "AUTL61": f"{loan.balloon_amount:.2f}" if loan.product == "PCP" else "ND5",
            "AUTL62": f"{loan.balloon_amount:.2f}" if loan.product == "PCP" else "ND5",
            "AUTL63": f"{loan.balloon_amount:.2f}" if loan.product == "PCP" else "ND5",
            "AUTL64": "ND5", "AUTL65": "ND5", "AUTL66": "ND5",
            "AUTL67": arrears_dates.get(lid, "ND5"),
            "AUTL68": f"{arrears * loan.monthly_instalment:.2f}" if not defaulted else "0.00",
            "AUTL69": str(arrears * 30), "AUTL70": STATUS_CODE[status],
            "AUTL71": "PDXX" if defaulted else "ND5",
            "AUTL72": f"{default_period.loc[lid, 'defaulted_balance']:.2f}" if defaulted else "0.00",
            "AUTL73": default_period.loc[lid, "period_end"] if defaulted else "ND5",
            "AUTL74": "ND5", "AUTL75": "ND5",
            "AUTL76": f"{recoveries_by_loan.get((lid, t), 0.0):.2f}" if defaulted else "ND5",
            "AUTL77": "ND5", "AUTL78": "0.00", "AUTL79": ORIGINATOR, "AUTL80": ORIGINATOR_LEI, "AUTL81": "GB",
            "AUTL82": ORIGINATOR, "AUTL83": ORIGINATOR_LEI, "AUTL84": "GB",
        })
        rows.append(rec)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[c for c, *_ in AUTL], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- 4. FCA investor report (SECN 12 Annex 12)

# Investor report template, non-ABCP securitisation: code, name, format.
IVSS = [
    ("IVSS1", "Unique Identifier", "{ALPHANUM-28}"), ("IVSS2", "Data Cut-Off Date", "{DATEFORMAT}"),
    ("IVSS3", "Securitisation Name", "{ALPHANUM-100}"), ("IVSS4", "Reporting Entity Name", "{ALPHANUM-100}"),
    ("IVSS5", "Reporting Entity Contact Person", "{ALPHANUM-256}"),
    ("IVSS6", "Reporting Entity Contact Telephone", "{TELEPHONE}"),
    ("IVSS7", "Reporting Entity Contact Emails", "{ALPHANUM-256}"), ("IVSS8", "Risk Retention Method", "{LIST}"),
    ("IVSS9", "Risk Retention Holder", "{LIST}"), ("IVSS10", "Underlying Exposure Type", "{LIST}"),
    ("IVSS11", "Risk Transfer Method", "{Y/N}"), ("IVSS12", "Trigger Measurements/Ratios", "{Y/N}"),
    ("IVSS13", "Revolving/Ramp-Up Period End-Date", "{DATEFORMAT}"),
    ("IVSS14", "Principal Recoveries In The Period", "{MONETARY}"),
    ("IVSS15", "Interest Recoveries In The Period", "{MONETARY}"),
    ("IVSS16", "Principal Collections In The Period", "{MONETARY}"),
    ("IVSS17", "Interest Collections In The Period", "{MONETARY}"),
    ("IVSS18", "Drawings Under Liquidity Facility", "{Y/N}"), ("IVSS19", "Securitisation Excess Spread", "{MONETARY}"),
    ("IVSS20", "Excess Spread Trapping Mechanism", "{Y/N}"), ("IVSS21", "Current Overcollateralisation", "{PERCENTAGE}"),
    ("IVSS22", "Annualised Constant Prepayment Rate", "{PERCENTAGE}"), ("IVSS23", "Dilutions", "{MONETARY}"),
    ("IVSS24", "Gross Charge Offs In The Period", "{MONETARY}"), ("IVSS25", "Repurchased Exposures", "{MONETARY}"),
    ("IVSS26", "Restructured Exposures", "{MONETARY}"), ("IVSS27", "Annualised Constant Default Rate", "{PERCENTAGE}"),
    ("IVSS28", "Defaulted Exposures", "{MONETARY}"), ("IVSS29", "Defaulted Exposures CRR", "{MONETARY}"),
    ("IVSS30", "Risk Weight Approach", "{LIST}"),
    ("IVSS31", "Obligor Probability Of Default in Range [0.00%,0.10%)", "{PERCENTAGE}"),
    ("IVSS32", "Obligor Probability Of Default in Range [0.10%,0.25%)", "{PERCENTAGE}"),
    ("IVSS33", "Obligor Probability Of Default in Range [0.25%,1.00%)", "{PERCENTAGE}"),
    ("IVSS34", "Obligor Probability Of Default in Range [1.00%,7.50%)", "{PERCENTAGE}"),
    ("IVSS35", "Obligor Probability Of Default in Range [7.50%,20.00%)", "{PERCENTAGE}"),
    ("IVSS36", "Obligor Probability Of Default in Range [20.00%,100.00%]", "{PERCENTAGE}"),
    ("IVSS37", "Bank Internal Loss Given Default Estimate", "{PERCENTAGE}"),
    ("IVSS38", "Arrears 1-29 Days", "{PERCENTAGE}"), ("IVSS39", "Arrears 30-59 Days", "{PERCENTAGE}"),
    ("IVSS40", "Arrears 60-89 Days", "{PERCENTAGE}"), ("IVSS41", "Arrears 90-119 Days", "{PERCENTAGE}"),
    ("IVSS42", "Arrears 120-149 Days", "{PERCENTAGE}"), ("IVSS43", "Arrears 150-179 Days", "{PERCENTAGE}"),
    ("IVSS44", "Arrears 180+ Days", "{PERCENTAGE}"),
]
IVSR = [("IVSR1", "Unique Identifier", "{ALPHANUM-28}"),
        ("IVSR2", "Original Test/Event/Trigger Identifier", "{ALPHANUM-1000}"),
        ("IVSR3", "New Test/Event/Trigger Identifier", "{ALPHANUM-1000}"), ("IVSR4", "Description", "{ALPHANUM-100000}"),
        ("IVSR5", "Threshold Level", "{NUMERIC}"), ("IVSR6", "Actual Value", "{NUMERIC}"), ("IVSR7", "Status", "{Y/N}"),
        ("IVSR8", "Cure Period", "{INTEGER-9999}"), ("IVSR9", "Calculation Frequency", "{INTEGER-9999}"),
        ("IVSR10", "Consequence for Breach", "{LIST}")]
IVSF = [("IVSF1", "Unique Identifier", "{ALPHANUM-28}"),
        ("IVSF2", "Original Cashflow Item Identifier", "{ALPHANUM-1000}"),
        ("IVSF3", "New Cashflow Item Identifier", "{ALPHANUM-1000}"), ("IVSF4", "Cashflow Item", "{ALPHANUM-1000}"),
        ("IVSF5", "Amount Paid During Period", "{MONETARY}"), ("IVSF6", "Available Funds Post", "{MONETARY}")]


def _p(x):
    """A {PERCENTAGE} value: per cent with four decimals (0.138497 -> '13.8497')."""
    return f"{x * 100:.4f}"


def write_ivs(rep, path):
    """The monthly investor report in the FCA template: sheets IVSS (one row), IVSR (one row per test),
    IVSF (one row per item of the priority of payments)."""
    p, a, tr, rf = rep["pool"], rep["arrears"], rep["triggers"], rep["reserve_fund"]
    notes_closing = sum(n["closing_balance"] for n in rep["notes"])
    smm_default = p["defaults"] / p["opening_balance"] if p["opening_balance"] else 0.0
    close = p["closing_balance"]
    share = lambda k: _p(a[f"{k}_instalments"]["balance"] / close) if close else _p(0)  # noqa: E731
    any_breach = tr["cumulative_default_ratio"]["breached"] or tr["arrears_90_ratio"]["breached"] or \
        tr["reserve_fund_shortfall"]["breached"]
    ivss = {
        "IVSS1": UNIQUE_ID, "IVSS2": rep["collection_period_end"], "IVSS3": ISSUER, "IVSS4": ORIGINATOR,
        "IVSS5": "Securitisation Reporting", "IVSS6": "+441164960000", "IVSS7": "reporting@kestrel.example",
        "IVSS8": "VSLC", "IVSS9": "ORIG", "IVSS10": "ALOL", "IVSS11": "Y", "IVSS12": "Y" if any_breach else "N",
        "IVSS13": "ND5", "IVSS14": f"{p['recoveries']:.2f}", "IVSS15": "0.00",
        "IVSS16": f"{p['principal_received'] + p['prepayments']:.2f}", "IVSS17": f"{p['interest_collections']:.2f}",
        "IVSS18": "N", "IVSS19": f"{rep['residual_to_originator']:.2f}", "IVSS20": "N",
        "IVSS21": _p(close / notes_closing - 1) if notes_closing else _p(0), "IVSS22": _p(p["cpr"]),
        "IVSS23": "0.00", "IVSS24": f"{p['defaults']:.2f}", "IVSS25": "0.00", "IVSS26": "0.00",
        "IVSS27": _p(1 - (1 - smm_default) ** 12), "IVSS28": f"{p['defaults']:.2f}", "IVSS29": "ND5",
        "IVSS30": "ND5", **{f"IVSS{i}": "ND5" for i in range(31, 38)},
        "IVSS38": _p(0), "IVSS39": share(1), "IVSS40": share(2), "IVSS41": share(3),
        "IVSS42": _p(0), "IVSS43": _p(0), "IVSS44": _p(0),
    }
    c, r9 = tr["cumulative_default_ratio"], tr["arrears_90_ratio"]
    ivsr = [
        ("CDR", "Cumulative Default Ratio: Cumulative Defaults divided by the Pool Balance at the Cut-off Date. "
                "Breached when above the limit for the Collection Period.", _p(c["limit"]), _p(c["value"]),
         c["breached"]),
        ("ARR90", "90+ Day Arrears Ratio: balance of the Loans with 3 instalments in arrears divided by the "
                  "Closing Pool Balance. Breached when above the limit.", _p(r9["limit"]), _p(r9["value"]),
         r9["breached"]),
        ("RFREQ", "Reserve Fund at the Required Amount: the Reserve Fund balance after the Payment Date compared "
                  "with the Reserve Fund Required Amount.", f"{rf['required']:.2f}", f"{rf['balance']:.2f}",
         tr["reserve_fund_shortfall"]["breached"]),
    ]
    remaining = rep["available_funds"]
    ivsf = []
    for i, w in enumerate(rep["waterfall"], start=1):
        remaining = round(remaining - w["paid"], 2)
        ivsf.append({"IVSF1": UNIQUE_ID, "IVSF2": f"PP{i:02d}", "IVSF3": f"PP{i:02d}", "IVSF4": w["item"],
                     "IVSF5": f"{w['paid']:.2f}", "IVSF6": f"{max(remaining, 0.0):.2f}"})

    wb = Workbook()
    ws = wb.active
    ws.title = "IVSS"
    _header(ws, 1, [c for c, *_ in IVSS])
    for j, (code, *_r) in enumerate(IVSS, start=1):
        ws.cell(row=2, column=j, value=ivss[code])
    ws = wb.create_sheet("IVSR")
    _header(ws, 1, [c for c, *_ in IVSR])
    for i, (tid, desc, thr, val, breached) in enumerate(ivsr, start=2):
        for j, v in enumerate([UNIQUE_ID, tid, tid, desc, thr, val, "Y" if breached else "N", "ND5", "1", "CHPP"],
                              start=1):
            ws.cell(row=i, column=j, value=v)
    ws = wb.create_sheet("IVSF")
    _header(ws, 1, [c for c, *_ in IVSF])
    for i, row in enumerate(ivsf, start=2):
        for j, (code, *_r) in enumerate(IVSF, start=1):
            ws.cell(row=i, column=j, value=row[code])
    _save(wb, path)


def cumulative_recoveries(recoveries):
    """{(loan_id, period): recoveries received on the loan up to the end of that period}."""
    out, total = {}, {}
    for t in range(1, 13):
        for lid, amount in recoveries.get(t, []):
            total[lid] = round(total.get(lid, 0.0) + amount, 2)
        for lid, amount in total.items():
            out[(lid, t)] = amount
    return out


def write_all(data, loans, perf, recoveries, reports, dirty, regional_by_period, deal, write_pdf, write_xlsx):
    """Write every real-format file. regional_by_period: {period: DataFrame of the Regional tab}."""
    cut_off = date.fromisoformat(deal["cut_off_date"])
    stem = "Kestrel_Thames_2026-1"
    for d in ["originator", "servicer_reports", "investor_reports", "loan_level"]:
        (data / d).mkdir(parents=True, exist_ok=True)
    write_pool_cut_autl(dirty, cut_off, deal["closing_date"],
                        data / "originator" / f"THAMES_2026-1_AUTL_Pool_Cut_{cut_off.isoformat()}.csv")
    write_supplementary(dirty, data / "originator" / f"{stem}_Supplementary_Data_{cut_off.isoformat()}.csv")
    write_data_dictionary(data / "originator" / f"{stem}_Data_Dictionary.xlsx", cut_off)
    rec_cum = cumulative_recoveries(recoveries)
    region_of = loans.set_index("loan_id").region
    product_of = loans.set_index("loan_id")["product"]
    for rep in reports:
        t = rep["period"]
        month = rep["collection_period_end"][:7]
        defaults_rows = [(r.loan_id, region_of[r.loan_id], product_of[r.loan_id], float(r.defaulted_balance))
                         for r in perf[(perf.period == t) & (perf.defaulted_balance > 0)].itertuples()]
        write_servicer_workbook(rep, regional_by_period[t], defaults_rows, t,
                                data / "servicer_reports" / f"{stem}_Servicer_Report_{month}.xlsx")
        write_loan_level_csv(perf, loans, t, data / "servicer_reports" / f"{stem}_Loan_Level_Data_{month}.csv")
        write_autl(perf, loans, rec_cum, t, deal["closing_date"],
                   data / "loan_level" / f"THAMES_2026-1_AUTL_{rep['collection_period_end']}.csv")
        write_ivs(rep, data / "loan_level" / f"THAMES_2026-1_IVS_{rep['collection_period_end']}.xlsx")
        stem_ir = data / "investor_reports" / f"Thames_2026-1_Investor_Report_{rep['payment_date']}"
        write_pdf(rep, reports, perf, loans, stem_ir.with_suffix(".pdf"))
        write_xlsx(rep, reports, stem_ir.with_suffix(".xlsx"))
