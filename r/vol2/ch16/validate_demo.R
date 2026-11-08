# Chapter 16: run the validation tool in R and compare the totals before and after cleaning.
# Run from the repository root: Rscript r/vol2/ch16/validate_demo.R
source("r/taragent/load.R")

tape <- read_tape()                                  # the tape exactly as received
issues <- find_issues(tape)                          # run the nine rules
cat(sprintf("Rows received: %s\n", comma0(nrow(tape))))
cat(sprintf("Issues found:  %d\n\n", length(issues)))
cat(sprintf("%-10s %-32s %s\n", "loan_id", "column", "rule"))
for (i in issues) cat(sprintf("%-10s %-32s %s\n", i$loan_id, i$column, i$rule))
clean <- clean_tape(tape, issues)                    # apply the safe fixes
cat(sprintf("\nBalance as received:  %s\n", money(sum(tape$current_balance))))
cat(sprintf("Balance after fixes:  %s\n", money(sum(clean$current_balance))))
cat(sprintf("Loans after fixes:    %s\n", comma0(nrow(clean))))
