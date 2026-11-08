"""Deal terms for Severn Residential Mortgages 2026-1 plc — the second, fictional prospectus.

A UK prime owner-occupied residential mortgage deal (RMBS), used in Volume 2 Part E to test
the Prospectus Analyser on a document whose layout and vocabulary differ from the Thames
prospectus. Every name is fictional. This file is the single source of truth: the
prospectus (build_rmbs_prospectus.py) and the answer key are both generated from it.
"""

DEAL = {
    "issuer": "Severn Residential Mortgages 2026-1 plc",
    "seller": "Marlowe Building Society",
    "mortgage_administrator": "Marlowe Building Society",
    "cash_manager": "Marlowe Building Society",
    "trustee": "Kingsgate Trustees Limited",
    "account_bank": "Halcyon Bank plc",
    "swap_provider": "Halcyon Bank plc",
    "arranger": "Halcyon Bank plc",
    "currency": "GBP",
    "portfolio_reference_date": "2026-03-31",   # the cut-off date
    "issue_date": "2026-05-14",                 # the closing date
    "first_interest_payment_date": "2026-07-20",
    "interest_payment_months": "January, April, July and October",
    "interest_payment_day": 20,
    "step_up_date": "2031-07-20",
    "final_maturity_date": "2064-07-20",
    "n_loans": 1912,
    "pool_balance": 400_000_000.00,
}

# Notes: principal amount, margin over Compounded Daily SONIA before and after the step-up date, rating.
# Class Z does not bear interest; it absorbs losses first.
CLASSES = [
    {"name": "A", "balance": 350_000_000.00, "margin": 0.0058, "step_up_margin": 0.0116, "rating": "AAAsf"},
    {"name": "B", "balance": 16_000_000.00, "margin": 0.0095, "step_up_margin": 0.01425, "rating": "AAsf"},
    {"name": "C", "balance": 12_000_000.00, "margin": 0.0135, "step_up_margin": 0.02025, "rating": "Asf"},
    {"name": "D", "balance": 10_000_000.00, "margin": 0.0210, "step_up_margin": 0.0315, "rating": "BBBsf"},
    {"name": "Z", "balance": 12_000_000.00, "margin": None, "step_up_margin": None, "rating": "Unrated"},
]

RESERVES = [
    # General Reserve Fund: 1.50 per cent of the Class A to D Notes at the Issue Date.
    {"name": "General Reserve Fund", "percent": 0.015, "basis": ["A", "B", "C", "D"], "can_cover_losses": True,
     "use": "covers shortfalls of senior expenses and interest on the Class A to D Notes, and debit balances on the "
            "Class A to D Principal Deficiency Ledgers; it does not cover the Class Z Notes"},
    # Liquidity Reserve Fund: 1.00 per cent of the Class A and B Notes; only for senior expenses and Class A and B interest.
    {"name": "Liquidity Reserve Fund", "percent": 0.010, "basis": ["A", "B"], "can_cover_losses": False,
     "use": "covers shortfalls of senior expenses and interest on the Class A and B Notes only"},
]

FEES = {
    "mortgage_administrator_fee": 0.0020,   # per year on the current balance of the portfolio
    "cash_manager_fee": 30_000.00,          # per year
    "trustee_fee": 20_000.00,               # per year
}

TRIGGERS = [
    {"name": "Arrears Trigger",
     "measure": "current balance of loans 3 or more months in arrears divided by the current balance of the portfolio",
     "limit": 0.025},
    {"name": "Cumulative Loss Trigger",
     "measure": "cumulative realised losses divided by the portfolio balance at the Issue Date",
     "limit": 0.004},
    {"name": "Reserve Trigger",
     "measure": "General Reserve Fund balance divided by the General Reserve Fund Required Amount",
     "limit": 0.85, "direction": "below"},
]
TRIGGER_CONSEQUENCE = "Sequential Payment Trigger: principal is paid sequentially, Class A first, permanently"

REVENUE_PRIORITY = [
    "Note Trustee and Security Trustee fees and expenses",
    "Mortgage Administrator, Cash Manager and Issuer Account Bank fees",
    "Net amounts due to the Swap Provider",
    "Interest on the Class A Notes",
    "Liquidity Reserve Fund top-up",
    "Class A Principal Deficiency Ledger",
    "Interest on the Class B Notes",
    "Class B Principal Deficiency Ledger",
    "Interest on the Class C Notes",
    "Class C Principal Deficiency Ledger",
    "Interest on the Class D Notes",
    "Class D Principal Deficiency Ledger",
    "General Reserve Fund top-up",
    "Class Z Principal Deficiency Ledger",
    "Subordinated swap termination payments",
    "Interest and principal on the Subordinated Loan",
    "Deferred consideration to the Seller",
]

PRINCIPAL_PRIORITY = [
    "Revenue shortfall",
    "Principal on the Class A Notes",
    "Principal on the Class B Notes",
    "Principal on the Class C Notes",
    "Principal on the Class D Notes",
    "Principal on the Class Z Notes",
    "Excess to Available Revenue Receipts",
]

LOAN_WARRANTIES = [
    "Each loan is secured by a first-ranking legal mortgage over a residential property in England or Wales, or by a "
    "first-ranking standard security over a residential property in Scotland.",
    "Each borrower is an individual who occupies the property as his or her main residence.",
    "No loan was more than 30 days in arrears on the Portfolio Reference Date.",
    "Each loan had made at least 3 monthly payments by the Portfolio Reference Date.",
    "The current loan-to-value ratio of each loan does not exceed 95 per cent.",
    "No loan is a buy-to-let, shared-ownership, right-to-buy or equity-release loan.",
    "Each loan was originated by the Seller between 2019 and 2025 under its lending criteria.",
    "The final maturity date of each loan falls no later than July 2061.",
    "Each loan is denominated in sterling and repayable in monthly instalments.",
    "No borrower is subject to a bankruptcy order or an individual voluntary arrangement.",
]

RISK_RETENTION = ("The Seller retains a material net economic interest of not less than 5 per cent of the "
                  "nominal value of the securitised exposures by holding randomly selected exposures, which would "
                  "otherwise have been securitised, from a pool of not less than 100 potentially securitised "
                  "exposures at origination, as required by the risk retention rules of the UK securitisation "
                  "framework (SECN 5 of the FCA Handbook and the Securitisation Part of the PRA Rulebook).")
RISK_RETENTION_METHOD = "randomly selected exposures"

DEFINITIONS = {
    "Arrears Ratio": "the aggregate current balance of the loans that are 3 or more months in arrears divided by "
                     "the aggregate current balance of the portfolio, on the last day of a collection period",
    "Cumulative Loss Ratio": "the aggregate of all realised losses since the Issue Date divided by the current "
                             "balance of the portfolio on the Issue Date",
    "Realised Loss": "the amount by which the balance of a loan exceeds the proceeds of enforcement after the "
                     "property has been sold",
    "Principal Deficiency Ledger": "a ledger, one sub-ledger per class, recording realised losses and principal "
                                   "used to pay revenue items, cleared from Available Revenue Receipts",
    "Step-Up Date": "the Interest Payment Date in July 2031, after which the margins step up and the Issuer may "
                    "redeem all the Notes",
}

# Pool stratifications at the Portfolio Reference Date: (label, share of balance, share of loans).
POOL_STATS = {
    "weighted_average_current_ltv": 0.648,
    "weighted_average_indexed_ltv": 0.583,
    "weighted_average_interest_rate": 0.0472,
    "weighted_average_seasoning_months": 21.4,
    "weighted_average_remaining_term_years": 24.6,
}
STRATS = {
    "Current loan-to-value": [("0% to 50%", 0.214, 0.298), ("50% to 60%", 0.161, 0.152), ("60% to 70%", 0.198, 0.181),
                              ("70% to 80%", 0.226, 0.204), ("80% to 90%", 0.152, 0.126), ("90% to 95%", 0.049, 0.039)],
    "Indexed loan-to-value": [("0% to 50%", 0.297, 0.381), ("50% to 60%", 0.188, 0.170), ("60% to 70%", 0.214, 0.192),
                              ("70% to 80%", 0.186, 0.160), ("80% to 90%", 0.093, 0.079), ("90% to 95%", 0.022, 0.018)],
    "Region": [("London", 0.192, 0.121), ("South East", 0.214, 0.186), ("South West", 0.098, 0.103),
               ("East of England", 0.112, 0.109), ("Midlands", 0.131, 0.152), ("North West", 0.094, 0.115),
               ("North East and Yorkshire", 0.071, 0.097), ("Wales", 0.038, 0.050), ("Scotland", 0.050, 0.067)],
    "Interest type": [("Fixed for 2 years", 0.284, 0.301), ("Fixed for 5 years", 0.533, 0.512),
                      ("Standard variable rate", 0.071, 0.088), ("Tracker (Bank Rate)", 0.112, 0.099)],
    "Borrower type": [("First-time buyer", 0.276, 0.312), ("Home mover", 0.389, 0.351), ("Remortgage", 0.335, 0.337)],
    "Repayment type": [("Capital and interest", 0.914, 0.931), ("Interest-only", 0.032, 0.021),
                       ("Part and part", 0.054, 0.048)],
}
