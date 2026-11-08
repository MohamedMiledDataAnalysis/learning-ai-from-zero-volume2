# Chapter 26: which reserve funds count in the credit enhancement, and why, read from each prospectus.
#   Rscript r/vol2/ch26/demo_reserves.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
for (deal in c("thames", "severn")) {
  terms <- run_extraction(sample_path(deal, "pdf"), "both", "simulated", deal)$terms
  a <- analyse_deal_terms(terms)
  cat("==", a$deal, "\n")
  for (i in seq_along(terms$reserve_funds)) {
    f <- terms$reserve_funds[[i]]$can_cover_losses
    r <- a$reserves[[i]]
    cat(sprintf("%s: %s\n", r$name, r$reason))
    cat(strwrap(sprintf("page %s: \"%s\"", f$page, f$quote), 96, indent = 2, exdent = 2), sep = "\n")
  }
  cat(sprintf("Class A credit enhancement: %.3f%%\n\n", 100 * a$credit_enhancement[[1]]$credit_enhancement))
}
