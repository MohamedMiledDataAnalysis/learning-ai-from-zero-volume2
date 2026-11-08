# Solution 20.4: which tool does the rule brain choose for each question?
source("r/taragent/load.R")

questions <- c("Validate the loan tape.",
               "What share of the pool balance at the cut-off date is PCP?",
               "Is principal paid pro rata or sequentially in period 9?",
               "According to the prospectus, what is the trustee fee?",
               "Draft the surveillance note for period 10.",
               "What is the weather in London?")
for (q in questions) {
  choice <- choose_tool(q)
  cat(sprintf("%-60s -> %s\n", q, if (is.null(choice)) "no tool" else paste0(choice$name, to_json(choice$arguments))))
}
