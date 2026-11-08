# Solution 23.5: do the Excel packs written by R and by Python hold the same values, sheet by sheet?
source("r/taragent/load.R")

folder <- tempfile()
dir.create(folder)
python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
code <- sprintf(paste0("import sys; sys.path.insert(0, 'python'); from tar_agent.export import export_monthly_pack; ",
                       "export_monthly_pack(10, %s)"),
                shQuote(normalizePath(file.path(folder, "py"), winslash = "/", mustWork = FALSE)))   # "/" also on Windows
system2(python, c("-c", shQuote(code)))
r_path <- export_monthly_pack(10, file.path(folder, "r"))
py_path <- file.path(folder, "py", "surveillance_pack_2026_10.xlsx")
# openpyxl stores "£" as the XML character reference "&#163;", which openxlsx's reader does not decode.
decode <- function(d) {
  d[] <- lapply(d, function(col) if (!is.character(col)) col else vapply(col, function(x) {
    if (is.na(x)) return(x)
    codes <- regmatches(x, gregexpr("&#[0-9]+;", x))[[1]]
    for (code in unique(codes)) x <- gsub(code, intToUtf8(as.integer(gsub("[&#;]", "", code))), x, fixed = TRUE)
    x
  }, "", USE.NAMES = FALSE))
  d
}
for (sheet in getSheetNames(r_path)) {
  a <- read.xlsx(r_path, sheet, colNames = FALSE)
  b <- decode(read.xlsx(py_path, sheet, colNames = FALSE))
  same <- isTRUE(all.equal(a, b, check.attributes = FALSE))
  cat(sprintf("%-18s R %2d x %d   Python %2d x %d   same values: %s\n", sheet, nrow(a), ncol(a), nrow(b), ncol(b), same))
}
unlink(folder, recursive = TRUE)
