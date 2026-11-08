# Solution 16.7: a tenth rule — the original loan-to-value must be 100% or less.
source("r/taragent/load.R")

tape <- read_tape()
tape <- tape[!duplicated(tape), ]
ltv <- tape$original_balance / tape$vehicle_value * 100
flagged <- tape[ltv > 100, ]
cat(sprintf("Loans with an original loan-to-value above 100%%: %d\n", nrow(flagged)))
cat(sprintf("Highest original loan-to-value: %.2f%%\n", max(ltv)))
