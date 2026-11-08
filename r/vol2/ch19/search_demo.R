# Chapter 19: three searches in R, and the known limitation of keyword search.
source("r/taragent/load.R")

for (q in c("What is the limit for the 90+ day arrears ratio?", "servicer fee", "Which loans were eligible?")) {
  cat("Query:", q, "\n")
  for (r in search_prospectus(q)$results) {
    cat(sprintf("  page %d  score %6.3f  %s...\n", r$page, r$score, substr(r$text, 1, 62)))
  }
  cat("\n")
}
