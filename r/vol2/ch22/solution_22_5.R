# Solution 22.5: what the evaluation prints when an answer is wrong. We change one expected value on purpose.
source("r/taragent/load.R")

questions <- load_questions()[c(4, 13)]                  # two of the 40 questions
questions[[2]]$expected$value <- 1.30                     # the true value is 1.6403 (period 12); 1.30 is wrong on purpose
out <- run_evaluation("rules", questions)
for (r in out$results) cat(sprintf("%s  %s  %s\n", r$id, if (r$correct) "RIGHT" else "WRONG", r$reason))
cat(sprintf("Score: %d / %d\n", as.integer(out$score), out$out_of))
