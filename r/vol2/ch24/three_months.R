# Chapter 24: three months of agentic surveillance in R (9 and 10 approved, 11 declined).
source("r/taragent/load.R")

folder <- tempfile()
for (month in list(c(9, TRUE), c(10, TRUE), c(11, FALSE))) {
  r <- run_surveillance(month[1], memory_dir = file.path(folder, "memory"), out_dir = file.path(folder, "out"),
                        approve = as.logical(month[2]))
  for (line in r$changes) cat("  memory:", line, "\n")
  cat("\n")
}
unlink(folder, recursive = TRUE)
