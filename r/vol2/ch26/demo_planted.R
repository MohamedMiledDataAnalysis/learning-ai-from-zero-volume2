# Chapter 26: the page grounding check catches a planted wrong value (Severn Class B margin 1.80% instead of 0.95%).
#   Rscript r/vol2/ch26/demo_planted.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
key <- jsonlite::fromJSON(sample_path("severn", "key"), simplifyVector = FALSE)
brain <- simulated_model_brain(key, plant = list("classes.B.margin" = 0.018))
terms <- extract_deal_terms(sample_path("severn", "pdf"), "model", brain)
cat("Model layer:", SIMULATED_LABEL, "- one value planted wrong\n")
t <- terms_table(terms)
print(t[t$Grounded == "NOT grounded", c("Field", "Value", "Page", "Grounded")], row.names = FALSE)
cat("\n", coverage_text(terms), "\n", sep = "")
