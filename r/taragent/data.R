# Where the deal pack lives, and small helpers to read it (R version of tar_agent/data.py).
#
# Every tool reads files through these functions, so the folder is set in one place.
# Set the environment variable TAR_DATA_DIR to use another copy of the data.

library(jsonlite)

DATA_DIR <- Sys.getenv("TAR_DATA_DIR", file.path(repo_root(), "data"))
N_PERIODS <- 12

STANDARD_REGIONS <- c(
  "London", "South East", "South West", "East of England", "East Midlands", "West Midlands",
  "North West", "North East", "Yorkshire and the Humber", "Wales", "Scotland", "Northern Ireland")

# A small cache: each file is read once per R session (the Python version uses lru_cache).
.cache <- new.env()
cached <- function(key, compute) {
  if (!exists(key, envir = .cache, inherits = FALSE)) assign(key, compute(), envir = .cache)
  get(key, envir = .cache)
}

deal_terms <- function() {
  cached("deal_terms", function() fromJSON(file.path(DATA_DIR, "deal_terms.json"), simplifyVector = FALSE))
}

# Write a value the way Python's repr() would, so error messages match the Python tools.
py_repr <- function(x) {
  if (length(x) == 0 || (length(x) == 1 && is.na(x))) return("None")
  if (is.character(x)) return(paste0("'", x, "'"))
  format(x)
}

# Python's list repr: ['a', 'b'].
py_list <- function(x) paste0("[", paste0("'", x, "'", collapse = ", "), "]")

check_period <- function(period) {
  ok <- is.numeric(period) && length(period) == 1 && !is.na(period) &&
    period == round(period) && period >= 1 && period <= N_PERIODS
  if (!ok) stop(sprintf("period must be a whole number from 1 to %d, not %s", N_PERIODS, py_repr(period)),
                call. = FALSE)
  invisible(TRUE)
}

# Period 1 -> "2026_01" (the part of the file names that identifies the month).
period_stem <- function(period) {
  check_period(period)
  sprintf("2026_%02d", as.integer(period))
}

investor_report <- function(period) {
  path <- file.path(DATA_DIR, "investor_reports", paste0("investor_report_", period_stem(period), ".json"))
  fromJSON(path, simplifyVector = FALSE)
}

servicer_report <- function(period) {
  read.csv(file.path(DATA_DIR, "servicer_reports", paste0("servicer_report_", period_stem(period), ".csv")),
           stringsAsFactors = FALSE)
}

loan_performance <- function() {
  cached("loan_performance", function()
    read.csv(file.path(DATA_DIR, "loan_performance.csv"), stringsAsFactors = FALSE))
}
