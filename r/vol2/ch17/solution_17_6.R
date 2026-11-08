# Solution 17.6: a new band — remaining term at the cut-off date, in three bands.
source("r/taragent/load.R")

pool <- pool_at(0)
band <- cut(pool$remaining_term_months, breaks = c(0, 12, 24, 60),
            labels = c("1-12 months", "13-24 months", "25-60 months"))
totals <- tapply(pool$balance, band, sum)
for (b in names(totals)) {
  cat(sprintf("  %-13s %16s  %6.2f%%\n", b, formatC(totals[[b]], format = "f", digits = 2, big.mark = ","),
              100 * totals[[b]] / sum(totals)))
}
