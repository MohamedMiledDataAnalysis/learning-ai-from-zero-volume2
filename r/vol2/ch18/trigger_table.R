# Chapter 18: the two trigger tests for all twelve periods, in R.
source("r/taragent/load.R")

cat(sprintf("%6s %10s %7s %18s %7s  mode\n", "Period", "90+ ratio", "limit", "Cum. default ratio", "limit"))
for (period in 1:12) {
  r <- run_trigger_tests(period)
  t <- setNames(r$tests, vapply(r$tests, function(x) x$test, ""))
  a <- t$arrears_90_ratio
  c <- t$cumulative_default_ratio
  flag <- if (a$breached || c$breached) " <- breach" else ""
  cat(sprintf("%6d %10s %7s %18s %7s  %s%s\n", period, pct(a$value), pct(a$limit), pct(c$value), pct(c$limit),
              r$principal_payment_mode, flag))
}
