# Chapter 26: the first rows of the deal-terms table the app shows (Severn, both layers, simulated model).
#   Rscript r/vol2/ch26/demo_table.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
run <- run_extraction(sample_path("severn", "pdf"), "both", "simulated", "severn")
cat(run$message, "\n\n")
t <- terms_table(run$terms)
t$Value <- substr(t$Value, 1, 26)                 # long names cut so the table fits the page
print(head(t[t$Field %in% c("deal_name", "pool_balance", "parties.servicer", "dates.closing",
                            "classes[0].balance", "classes[0].margin", "triggers[0].limit"), c("Field", "Value", "Page", "Source", "Grounded")], 7), row.names = FALSE)
