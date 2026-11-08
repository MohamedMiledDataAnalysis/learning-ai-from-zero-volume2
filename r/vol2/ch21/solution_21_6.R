# Solution 21.6: a "Watch list" section: regions with more than 1% of their own balance 90+ days in arrears.
source("r/taragent/load.R")

watch_list <- function(period, threshold = 0.01) {
  rows <- stratify_pool("region", period, "balance_90plus")$rows
  flagged <- Filter(function(r) r$ratio_within_group > threshold, rows)
  lines <- if (length(flagged) == 0) "- No region above the threshold." else
    vapply(flagged, function(r) sprintf("- %s: %s of its balance is 90+ days in arrears.", r$group,
                                        pct(r$ratio_within_group, 1)), "")
  paste(c("## Watch list", lines), collapse = "\n")
}
for (p in c(4, 10)) cat(sprintf("Period %d\n%s\n\n", p, watch_list(p)))
