# Chapter 26: the analysis tab in text form, for both prospectuses.
#   Rscript r/vol2/ch26/demo_analyse.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
for (deal in c("thames", "severn")) {
  terms <- run_extraction(sample_path(deal, "pdf"), "both", "simulated", deal)$terms
  a <- analyse_deal_terms(terms)
  cat("==", a$deal, "\n")
  print(ce_table(a)[, c("Class", "Share of notes", "Subordination", "Reserve support", "Credit enhancement")], row.names = FALSE)
  ck <- checks_table(a)
  cat(sprintf("Checks: %s\n", paste(sprintf("%s (%s)", ck$Check, ck$Result), collapse = "; ")) |> strwrap(78) |> paste(collapse = "\n"), "\n")
  cat(sprintf("Waterfall: %s\n\n", paste(sprintf("%s %d steps", names(waterfall_steps(a)), lengths(waterfall_steps(a))), collapse = ", ")))
}
