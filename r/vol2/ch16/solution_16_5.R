# Solution 16.5: how many problems each rule finds, largest first.
source("r/taragent/load.R")

issues <- find_issues(read_tape())
rules <- vapply(issues, function(i) i$rule, "")
counts <- sort(table(rules), decreasing = TRUE)
for (r in names(counts)) cat(sprintf("%2d  %s\n", counts[[r]], r))
