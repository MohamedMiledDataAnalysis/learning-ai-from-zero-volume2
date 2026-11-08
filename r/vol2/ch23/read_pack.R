# Chapter 23: export the pack for period 10 from R and read it back.
source("r/taragent/load.R")

folder <- tempfile()
path <- export_monthly_pack(10, folder)
cat("File:", basename(path), "\n")
for (sheet in getSheetNames(path)) {
  d <- read.xlsx(path, sheet, colNames = FALSE)
  cat(sprintf("Sheet '%s': %d rows x %d columns\n", sheet, nrow(d), ncol(d)))
}
cat("\n")
print(read.xlsx(path, "Triggers", sep.names = " "), row.names = FALSE)
unlink(folder, recursive = TRUE)
