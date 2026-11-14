# Chapter 26: the deal check. The Thames prospectus, its pool-cut tape and the investor report for period 10,
# checked against each other.
#   Rscript r/vol2/ch26/demo_deal_check.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })

terms <- extract_deal_terms(sample_path("thames", "pdf"), "rules")
files <- tape_files(c(POOL_CUT, SUPPLEMENTARY))                 # the upload box gives the two files in any order
report <- investor_report_path(10)                               # Larkmead's PDF; its Excel copy gives the same
checks <- deal_check(terms, files$template, report, files$supplementary)
options(width = 110)
checks$Check <- substr(checks$Check, 1, 40)
names(checks)[names(checks) == "Prospectus page"] <- "Page"
print(checks[, c("Check", "Page", "Found", "Result")], row.names = FALSE, right = FALSE)
