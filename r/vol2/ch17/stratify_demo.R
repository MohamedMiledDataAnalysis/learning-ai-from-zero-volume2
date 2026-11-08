# Chapter 17: three stratifications of the pool, in R.
source("r/taragent/load.R")

show <- function(title, s) {
  measure <- s$measure
  cat(title, "\n")
  for (r in s$rows) {
    extra <- if (!is.null(r$ratio_within_group)) sprintf("  within region %6.2f%%", r$ratio_within_group * 100) else ""
    cat(sprintf("  %-26s %16s  %6.2f%%%s\n", r$group, formatC(r[[measure]], format = "f", digits = 2, big.mark = ","),
                r$share_of_total * 100, extra))
  }
  cat(sprintf("  %-26s %16s\n\n", "Total", formatC(s$total, format = "f", digits = 2, big.mark = ",")))
}
show("1. Balance by product at the cut-off date", stratify_pool("product", 0))
show("2. Balance by credit score band at the cut-off date", stratify_pool("credit_score_band", 0))
show("3. 90+ day arrears by region, end of period 10", stratify_pool("region", 10, "balance_90plus"))
