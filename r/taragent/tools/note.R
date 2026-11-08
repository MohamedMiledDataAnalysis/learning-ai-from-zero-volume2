# Tool 5 — draft the monthly surveillance note (R version of tar_agent/tools/note.py).
#
# Builds the factual draft from the other tools: every figure is computed, none invented.

pct <- function(x, dp = 2) sprintf(paste0("%.", dp, "f%%"), x * 100)
money0 <- function(x) paste0("£", formatC(x, format = "f", digits = 0, big.mark = ","))

# Tool entry point: the note as Markdown, plus the key figures it uses.
draft_surveillance_note <- function(period) {
  check_period(period)
  rep <- investor_report(period)
  trig <- run_trigger_tests(period)
  pool <- rep$pool
  test_named <- function(tr, name) Filter(function(t) t$test == name, tr$tests)[[1]]
  a90 <- test_named(trig, "arrears_90_ratio")
  cdr <- test_named(trig, "cumulative_default_ratio")
  prev_a90 <- if (period > 1) test_named(run_trigger_tests(period - 1), "arrears_90_ratio")$value else 0

  regions <- stratify_pool("region", period, "balance_90plus")$rows
  top <- if (length(regions) > 0 && regions[[1]]$balance_90plus > 0) regions[[1]] else NULL
  if (!is.null(top)) {
    by_balance <- stratify_pool("region", period, "balance")$rows
    pool_share <- Filter(function(r) r$group == top$group, by_balance)[[1]]$share_of_total
  }

  if (trig$trigger_event_this_period && !is.null(trig$first_breach_period) && trig$first_breach_period == period) {
    headline <- "A trigger event occurred this period. Principal is now paid sequentially."
  } else if (trig$principal_payment_mode == "sequential") {
    headline <- sprintf("Principal remains sequential since the trigger event in period %d.",
                        as.integer(trig$first_breach_period))
  } else {
    headline <- "All trigger tests passed. Principal continues to be paid pro rata."
  }
  verdict <- function(t) if (t$breached) "BREACHED" else "pass"
  agree <- all(vapply(trig$tests, function(t) t$agrees_with_report, logical(1)))

  lines <- c(
    paste0("# Surveillance note — ", rep$deal),
    sprintf("Collection period %d (ending %s), payment date %s", as.integer(period),
            rep$collection_period_end, rep$payment_date),
    "",
    paste0("**", headline, "**"),
    "",
    "## Pool",
    sprintf("- Pool balance fell from %s to %s (%s loans).", money0(pool$opening_balance),
            money0(pool$closing_balance), formatC(pool$loans_outstanding, format = "d", big.mark = ",")),
    sprintf("- Prepayments: %s. Defaults: %s. Recoveries: %s.", money0(pool$prepayments),
            money0(pool$defaults), money0(pool$recoveries)),
    "",
    "## Trigger tests",
    sprintf("- 90+ day arrears ratio: %s against a limit of %s — %s (previous period %s).",
            pct(a90$value), pct(a90$limit), verdict(a90), pct(prev_a90)),
    sprintf("- Cumulative default ratio: %s against a limit of %s — %s.", pct(cdr$value), pct(cdr$limit),
            verdict(cdr)),
    sprintf("- Reserve fund: %s (required %s).", money0(rep$reserve_fund$balance),
            money0(rep$reserve_fund$required)),
    sprintf("- Figures recomputed from the loan-level data %s with the investor report.",
            if (agree) "agree" else "DO NOT agree")
  )
  if (!is.null(top)) {
    lines <- c(lines, "", "## Driver",
               sprintf("- %s holds %s of the 90+ day arrears balance but %s of the pool balance. %s of its balance is 90+ days in arrears.",
                       top$group, pct(top$share_of_total, 1), pct(pool_share, 1), pct(top$ratio_within_group, 1)))
  }
  lines <- c(lines, "", "## Notes",
             vapply(rep$notes, function(n) sprintf("- Class %s: %s after %s of principal.", n$class,
                                                   money0(n$closing_balance), money0(n$principal_paid)), ""))
  if (rep$principal_deficiency > 0) {      # the notes exceed the pool: investors must be told
    lines <- c(lines, sprintf("- Principal deficiency after the payment date: %s.", money0(rep$principal_deficiency)))
  }
  list(
    period = period,
    note_markdown = paste(lines, collapse = "\n"),
    key_figures = list(
      arrears_90_ratio = a90$value, cumulative_default_ratio = cdr$value,
      principal_payment_mode = trig$principal_payment_mode,
      main_arrears_region = if (is.null(top)) NULL else top$group)
  )
}
