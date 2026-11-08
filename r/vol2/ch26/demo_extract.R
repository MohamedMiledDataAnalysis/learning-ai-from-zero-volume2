# Chapter 26: the extraction behind the app, on the book's two prospectuses.
#   Rscript r/vol2/ch26/demo_extract.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })

for (deal in c("thames", "severn")) {
  pdf <- sample_path(deal, "pdf")
  key <- jsonlite::fromJSON(sample_path(deal, "key"), simplifyVector = FALSE)
  for (layer in c("rules", "both")) {
    run <- run_extraction(pdf, layer, "simulated", deal)
    s <- score_against_key(run$terms, key)
    cat(sprintf("%-7s %-17s %2d of 16 fields | answer key %2d of %2d correct | not grounded: %d\n",
                deal, if (layer == "rules") "rules" else "both (simulated)", run$terms$coverage$found,
                s$correct, s$fields, length(run$terms$ungrounded)))
  }
}
cat("simulated = the simulated model: answers from the answer key, for teaching (not a language model)\n")
cat("\nSevern, rules only, missing fields:\n")
terms <- extract_deal_terms(sample_path("severn", "pdf"), "rules")
cat(strwrap(paste(unlist(terms$coverage$missing), collapse = ", "), 78, prefix = "  "), sep = "\n")
