# testthat runs every helper-*.R file before the tests: this one finds the repository root.
local_find_root <- function(dir = getwd()) {
  dir <- normalizePath(dir)
  while (!file.exists(file.path(dir, "requirements.txt"))) {
    if (dirname(dir) == dir) stop("cannot find the repository root")
    dir <- dirname(dir)
  }
  dir
}
root <- local_find_root()
if (!isTRUE(l10n_info()[["UTF-8"]])) invisible(suppressWarnings(Sys.setlocale("LC_CTYPE", "C.UTF-8")))   # read and compare text such as "€" as UTF-8
