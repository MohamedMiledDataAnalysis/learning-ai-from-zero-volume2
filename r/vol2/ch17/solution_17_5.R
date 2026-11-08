# Solution 17.5: the share of PCP loans in the pool balance, at the cut-off date and at the end of period 12.
source("r/taragent/load.R")

pcp_share <- function(period) {
  rows <- stratify_pool("product", period)$rows
  Filter(function(r) r$group == "PCP", rows)[[1]]$share_of_total
}
for (p in c(0, 12)) cat(sprintf("Period %2d: PCP share %s\n", p, pct(pcp_share(p))))
