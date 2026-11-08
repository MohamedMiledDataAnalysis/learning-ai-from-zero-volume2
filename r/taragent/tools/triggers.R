# Tool 3 — trigger tests (R version of tar_agent/tools/triggers.py).
#
# Recomputes the cumulative default ratio and the 90+ day arrears ratio from the
# loan-level data, compares them with the limits in the deal terms, and checks that
# the investor report shows the same figures.

cum_default_limit <- function(period) {
  for (s in deal_terms()$triggers$cum_default_schedule) {
    if (s[[1]] <= period && period <= s[[2]]) return(s[[3]])
  }
  stop(sprintf("no cumulative default limit for period %s", period), call. = FALSE)
}

# Both ratios computed from the loan-level data for one period.
recompute <- function(period) {
  perf <- loan_performance()
  p <- perf[perf$period == period, ]
  live <- p[p$status %in% c("Current", "Arrears"), ]
  pool_balance <- sum(live$closing_balance)
  arrears_90 <- sum(live$closing_balance[live$instalments_in_arrears >= 3])
  cum_defaults <- sum(perf$defaulted_balance[perf$period <= period])
  list(
    pool_balance = round(pool_balance, 2),
    arrears_90_balance = round(arrears_90, 2),
    arrears_90_ratio = arrears_90 / pool_balance,
    cumulative_defaults = round(cum_defaults, 2),
    cumulative_default_ratio = cum_defaults / deal_terms()$initial_pool_balance
  )
}

# The first period in which any test failed, or NULL.
first_breach_period <- function(up_to = N_PERIODS) {
  for (t in seq_len(up_to)) {
    r <- recompute(t)
    if (r$cumulative_default_ratio > cum_default_limit(t) ||
        r$arrears_90_ratio > deal_terms()$triggers$arrears_90_limit ||
        isTRUE(investor_report(t)$triggers$reserve_fund_shortfall$breached)) {
      return(t)
    }
  }
  NULL
}

# Tool entry point: the result of each test for one period, with headroom and a check against the report.
run_trigger_tests <- function(period) {
  check_period(period)
  terms <- deal_terms()
  report <- investor_report(period)
  breached_before <- first_breach_period(up_to = period - 1)
  limits <- list(cumulative_default_ratio = cum_default_limit(period),
                 arrears_90_ratio = terms$triggers$arrears_90_limit)
  values <- recompute(period)
  tests <- list()
  for (name in names(limits)) {
    value <- values[[name]]
    reported <- report$triggers[[name]]$value
    tests[[length(tests) + 1]] <- list(
      test = name,
      value = round(value, 6),
      limit = limits[[name]],
      headroom = round(limits[[name]] - value, 6),   # negative headroom means the limit is exceeded
      breached = value > limits[[name]],
      reported_value = reported,
      agrees_with_report = abs(value - reported) < 1e-6
    )
  }
  shortfall <- isTRUE(report$triggers$reserve_fund_shortfall$breached)
  breached_now <- any(vapply(tests, function(t) t$breached, logical(1))) || shortfall
  first <- if (!is.null(breached_before)) breached_before else if (breached_now) period else NULL
  list(
    period = period,
    payment_date = report$payment_date,
    tests = tests,
    reserve_fund_shortfall = shortfall,
    trigger_event_this_period = breached_now,
    first_breach_period = first,
    principal_payment_mode = if (!is.null(first)) "sequential" else "pro rata",
    report_shows_mode = if (isTRUE(report$triggers$sequential_payment)) "sequential" else "pro rata"
  )
}
