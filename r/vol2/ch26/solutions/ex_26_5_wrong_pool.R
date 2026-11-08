# Exercise 26.5: change one extracted value by hand and watch the page grounding check refuse it.
#   Rscript r/vol2/ch26/solutions/ex_26_5_wrong_pool.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
pdf <- sample_path("thames", "pdf")
terms <- extract_deal_terms(pdf, "rules")
cat("Extracted pool balance:", show_value("pool_balance", terms$pool_balance$value), "\n")
terms$pool_balance$value <- 74075862.24 + 1000          # a typing error of £1,000
checked <- ground_terms(terms, pdf)
cat("After the change, grounded:", checked$terms$pool_balance$grounded, "\n")
cat("Paths that failed:", paste(checked$failed, collapse = ", "), "\n")
