# Solution 24.5: what happens when the self-check fails? We spoil one figure on purpose.
source("r/taragent/load.R")

results <- run_plan(rule_plan(10), log = function(m) invisible(NULL))
check <- self_check(results, 10)
cat(sprintf("Untouched results: agree = %s\n", check$agree))
# Spoil the 90+ total of the stratification by £10,000, as a bug in a tool would.
for (i in seq_along(results)) {
  if (identical(results[[i]]$step$arguments$measure, "balance_90plus")) {
    results[[i]]$result$total <- results[[i]]$result$total + 10000
  }
}
check <- self_check(results, 10)
cat(sprintf("Spoilt results:    trigger tool %.6f, recomputed %.6f, agree = %s\n",
            check$trigger_tool, check$recomputed, check$agree))
