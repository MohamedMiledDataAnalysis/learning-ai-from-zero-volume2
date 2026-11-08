"""Tool 3 — trigger tests.

The prospectus (section 6) sets limits on the cumulative default ratio and the
90+ day arrears ratio. When a limit is exceeded, principal switches from pro
rata to sequential payment, permanently.

This tool does not trust the investor report: it recomputes both ratios from the
loan-level data, compares them with the limits in the deal terms, and checks
that the report shows the same figures.
"""

from ..data import N_PERIODS, check_period, deal_terms, investor_report, loan_performance


def cum_default_limit(period):
    for first, last, limit in deal_terms()["triggers"]["cum_default_schedule"]:
        if first <= period <= last:
            return limit
    raise ValueError(f"no cumulative default limit for period {period}")


def recompute(period):
    """Both ratios computed from the loan-level data for one period."""
    perf = loan_performance()
    p = perf[perf.period == period]
    live = p[p.status.isin(["Current", "Arrears"])]
    pool_balance = float(live.closing_balance.sum())
    arrears_90 = float(live[live.instalments_in_arrears >= 3].closing_balance.sum())
    cum_defaults = float(perf[perf.period <= period].defaulted_balance.sum())
    return {
        "pool_balance": round(pool_balance, 2),
        "arrears_90_balance": round(arrears_90, 2),
        "arrears_90_ratio": arrears_90 / pool_balance,
        "cumulative_defaults": round(cum_defaults, 2),
        "cumulative_default_ratio": cum_defaults / deal_terms()["initial_pool_balance"],
    }


def run_trigger_tests(period):
    """Tool entry point: the result of each test for one period, with headroom and a check against the report."""
    check_period(period)
    terms = deal_terms()
    report = investor_report(period)["triggers"]
    breached_before = first_breach_period(up_to=period - 1)
    tests = []
    for name, limit in [("cumulative_default_ratio", cum_default_limit(period)),
                        ("arrears_90_ratio", terms["triggers"]["arrears_90_limit"])]:
        value = recompute(period)[name]
        reported = report[name]["value"]
        tests.append({
            "test": name,
            "value": round(value, 6),
            "limit": limit,
            "headroom": round(limit - value, 6),   # negative headroom means the limit is exceeded
            "breached": value > limit,
            "reported_value": reported,
            "agrees_with_report": abs(value - reported) < 1e-6,
        })
    breached_now = any(t["breached"] for t in tests) or report["reserve_fund_shortfall"]["breached"]
    return {
        "period": period,
        "payment_date": investor_report(period)["payment_date"],
        "tests": tests,
        "reserve_fund_shortfall": report["reserve_fund_shortfall"]["breached"],
        "trigger_event_this_period": breached_now,
        "first_breach_period": breached_before or (period if breached_now else None),
        "principal_payment_mode": "sequential" if (breached_before or breached_now) else "pro rata",
        "report_shows_mode": "sequential" if report["sequential_payment"] else "pro rata",
    }


def first_breach_period(up_to=N_PERIODS):
    """The first period in which any test failed, or None."""
    for t in range(1, up_to + 1):
        r = recompute(t)
        if (r["cumulative_default_ratio"] > cum_default_limit(t)
                or r["arrears_90_ratio"] > deal_terms()["triggers"]["arrears_90_limit"]
                or investor_report(t)["triggers"]["reserve_fund_shortfall"]["breached"]):
            return t
    return None
