"""Deal terms for Thames Auto Receivables 2026-1 plc.

Every name in this deal is fictional. The terms below are the single source
of truth: the data generator, the investor reports and the prospectus all
read them from here, so the three can never disagree.
"""

SEED = 20260131

DEAL = {
    "issuer": "Thames Auto Receivables 2026-1 plc",
    "originator": "Kestrel Motor Finance Ltd",
    "servicer": "Kestrel Motor Finance Ltd",
    "trustee": "Albion Trustee Services Ltd",
    "currency": "GBP",
    "cut_off_date": "2025-12-31",
    "closing_date": "2026-01-28",
    "first_payment_date": "2026-02-20",
    "payment_day": 20,               # notes pay on the 20th of the month after each collection period
    "n_periods": 12,                 # collection periods January 2026 to December 2026
    "n_loans": 5000,
}

# Capital structure: share of the initial pool balance, margin over SONIA, rating.
CLASSES = [
    {"name": "A", "share": 0.85, "margin": 0.0070, "rating": "AAA"},
    {"name": "B", "share": 0.06, "margin": 0.0130, "rating": "AA"},
    {"name": "C", "share": 0.05, "margin": 0.0210, "rating": "A"},
    {"name": "D", "share": 0.04, "margin": 0.0350, "rating": "BBB"},
]

# Annual SONIA rate applying to each collection period (given in each investor report).
SONIA = [0.0395, 0.0395, 0.0390, 0.0385, 0.0385, 0.0380,
         0.0380, 0.0375, 0.0375, 0.0370, 0.0370, 0.0370]

FEES = {
    "servicer_fee_rate": 0.0100,     # per year, on the pool balance at the start of the period
    "trustee_fee_monthly": 2500.00,  # fixed amount per payment date
}

RESERVE_FUND = {
    "required_pct_of_initial_notes": 0.015,  # funded at closing, target stays fixed
    "can_cover_losses": False,               # pays items 1-5 (fees and interest) only, never principal
}

TRIGGERS = {
    # Cumulative default ratio = cumulative defaulted principal / initial pool balance.
    "cum_default_schedule": [(1, 6, 0.0100), (7, 12, 0.0200)],   # (first period, last period, limit)
    # 90+ day arrears ratio = balance of non-defaulted loans 3 or more instalments in arrears / pool balance.
    "arrears_90_limit": 0.0125,
    # Reserve fund below its required amount after the payment date.
    "reserve_fund_shortfall": True,
}

DEFINITIONS = {
    "default": "A loan is defaulted when it is 4 instalments in arrears.",
    "pool_balance": "Sum of the outstanding principal of all loans that are not defaulted, prepaid or repaid.",
    "recovery_rate": 0.55,           # share of the defaulted balance recovered
    "recovery_lag": 3,               # periods between default and recovery
}

# Behaviour assumptions used only by the generator (not part of the deal terms).
BEHAVIOUR = {
    "cpr": 0.15,                     # annual constant prepayment rate
    "p_miss_base": 0.009,            # monthly probability a current loan misses an instalment
    "p_cure": 0.30,                  # loan in arrears pays all arrears
    "p_stay": 0.50,                  # loan in arrears pays one instalment (arrears unchanged)
    "stress_region": "North West",   # a regional employer closure hits this region
    "stress_from_period": 3,
    "stress_miss_multiplier": 14.0,
    "stress_cure": 0.04,
    "stress_stay": 0.72,
}
