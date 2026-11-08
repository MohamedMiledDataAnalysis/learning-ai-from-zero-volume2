# Solution 23.4: export the packs for the last quarter of 2026 in one loop.
source("r/taragent/load.R")

folder <- tempfile()
for (period in 10:12) {
  path <- export_monthly_pack(period, folder)
  mode <- read.xlsx(path, "Summary", colNames = FALSE)[11, 2]
  cat(sprintf("%s  principal paid: %s\n", basename(path), mode))
}
unlink(folder, recursive = TRUE)
