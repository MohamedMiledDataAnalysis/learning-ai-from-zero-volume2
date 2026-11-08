# Chapter 26: the trigger tests rerun with the limits read from the Thames prospectus.
#   Rscript r/vol2/ch26/demo_surveillance.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
terms <- extract_deal_terms(sample_path("thames", "pdf"), "rules")
s <- surveillance_table(terms)
print(s[8:12, ], row.names = FALSE)
cat(sprintf("\nPeriods that agree with the agent's trigger tool: %d of %d\n", sum(s$`Agent agrees` == "yes"), nrow(s)))
