# Solution 18.6: in which period would the 90+ day arrears test first fail with other limits?
source("r/taragent/load.R")

ratios <- vapply(1:12, function(p) recompute(p)$arrears_90_ratio, 0)
for (limit in c(0.0100, 0.0125, 0.0150, 0.0175)) {
  first <- which(ratios > limit)[1]
  cat(sprintf("Limit %s: %s\n", pct(limit), if (is.na(first)) "no breach in 2026" else paste("first breach in period", first)))
}
