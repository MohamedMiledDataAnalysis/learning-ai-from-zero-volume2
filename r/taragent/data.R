# Where the deal pack lives, and small helpers to read it (R version of tar_agent/data.py).
#
# Every tool reads files through these functions, so the folder is set in one place.
# Set the environment variable TAR_DATA_DIR to use another copy of the data.
#
# The deal pack holds the files the parties really send: Kestrel's pool-cut tape and data
# dictionary (Excel), Kestrel's monthly servicer report (Excel) and loan-level data (CSV),
# Larkmead Bank's investor report (PDF) and the FCA loan-level file (AUTL1 to AUTL84).
# The functions below give each one short working names (loan_id, current_balance, ...).

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

# Period 1 -> "2026-02-20": the payment date that follows the collection period.
payment_date <- function(period) {
  check_period(period)
  day <- deal_terms()$deal$payment_day
  if (period < 12) sprintf("2026-%02d-%02d", as.integer(period) + 1L, day) else sprintf("2027-01-%02d", day)
}

investor_report_path <- function(period) {
  file.path(DATA_DIR, "investor_reports", paste0("Thames_2026-1_Investor_Report_", payment_date(period), ".pdf"))
}

# The cash manager's investor report for one period, read from its PDF (tools/investor_report.R).
investor_report <- function(period) read_investor_report(investor_report_path(period))

# The servicer's column names (Regional tab of the servicer report) and the working names.
REGIONAL_NAMES <- c(
  "Collection Period" = "period", "Region" = "region", "Live Agreements" = "loans_outstanding",
  "Outstanding Capital Balance" = "balance", "Balance 1 Instalment in Arrears" = "balance_1_in_arrears",
  "Balance 2 Instalments in Arrears" = "balance_2_in_arrears",
  "Balance 3 Instalments in Arrears" = "balance_3_in_arrears", "Defaults in Period" = "defaults",
  "Early Settlements in Period" = "prepayments")

month_stem <- function(period) sub("_", "-", period_stem(period), fixed = TRUE)

servicer_report_path <- function(period) {
  file.path(DATA_DIR, "servicer_reports", paste0("Kestrel_Thames_2026-1_Servicer_Report_", month_stem(period), ".xlsx"))
}

# The regional table of the servicer report: one row per region.
servicer_report <- function(period) {
  path <- servicer_report_path(period)
  table <- rename_columns(as.data.frame(readxl::read_excel(path, sheet = "Regional")), REGIONAL_NAMES, basename(path))
  table$period <- as.integer(table$period)
  table$loans_outstanding <- as.integer(table$loans_outstanding)
  table
}

# The loan-level data file sent with each servicer report.
LOAN_LEVEL_NAMES <- c(
  "Agreement Number" = "loan_id", "Collection Period" = "period", "Period End Date" = "period_end",
  "Product Type" = "product", "New/Used" = "vehicle_type", "Fuel Type" = "fuel_type",
  "Amount Financed" = "original_balance", "Customer Rate %" = "interest_rate_pct",
  "Bureau Score at Origination" = "credit_score", "Region" = "region", "Postcode Area" = "postcode_area",
  "Final Instalment Date" = "maturity_date", "Opening Capital Balance" = "opening_balance",
  "Instalments Paid" = "instalments_paid", "Scheduled Capital Received" = "principal_paid",
  "Interest Received" = "interest_paid", "Early Settlement Amount" = "prepayment",
  "Default Balance" = "defaulted_balance", "Closing Capital Balance" = "closing_balance",
  "Instalments in Arrears" = "instalments_in_arrears", "Account Status" = "status")
# The servicer's words for the status of an agreement, and the working words.
STATUS_NAMES <- c("Current" = "Current", "Arrears" = "Arrears", "Defaulted" = "Defaulted",
                  "Settled Early" = "Prepaid", "Paid Out" = "Repaid")
PERFORMANCE_COLUMNS <- c("loan_id", "period", "period_end", "opening_balance", "instalments_paid", "principal_paid",
                         "interest_paid", "prepayment", "defaulted_balance", "closing_balance",
                         "instalments_in_arrears", "status")
STATIC_COLUMNS <- c("loan_id", "product", "vehicle_type", "fuel_type", "original_balance", "interest_rate_pct",
                    "credit_score", "region", "postcode_area", "maturity_date")

loan_level_path <- function(period) {
  file.path(DATA_DIR, "servicer_reports", paste0("Kestrel_Thames_2026-1_Loan_Level_Data_", month_stem(period), ".csv"))
}

# The servicer's loan-level data for one period, with working names.
loan_level_data <- function(period) {
  path <- loan_level_path(period)
  table <- read.csv(path, stringsAsFactors = FALSE, na.strings = character(0), check.names = FALSE)
  table <- rename_columns(table, LOAN_LEVEL_NAMES, basename(path))
  table$status <- unname(STATUS_NAMES[table$status])
  table
}

loan_level_all <- function() {
  cached("loan_level_all", function() do.call(rbind, lapply(seq_len(N_PERIODS), loan_level_data)))
}

# The FCA loan-level file for one period, as received: field codes AUTL1 to AUTL84, every value as text.
fca_loan_level <- function(period) {
  check_period(period)
  end <- format(seq(as.Date(sprintf("2026-%02d-01", as.integer(period))), by = "month", length.out = 2)[2] - 1)
  read.csv(file.path(DATA_DIR, "loan_level", paste0("THAMES_2026-1_AUTL_", end, ".csv")),
           colClasses = "character", na.strings = character(0))
}

# The FCA investor report for one period (template SECN 12 Annex 12), as received: a list of three tables,
# IVSS (securitisation information), IVSR (tests and triggers) and IVSF (priority of payments).
fca_investor_report <- function(period) {
  check_period(period)
  end <- format(seq(as.Date(sprintf("2026-%02d-01", as.integer(period))), by = "month", length.out = 2)[2] - 1)
  path <- file.path(DATA_DIR, "loan_level", paste0("THAMES_2026-1_IVS_", end, ".xlsx"))
  sheets <- c("IVSS", "IVSR", "IVSF")
  setNames(lapply(sheets, function(s) as.data.frame(readxl::read_excel(path, sheet = s, col_types = "text"))), sheets)
}

rename_columns <- function(table, names_map, file_name) {
  missing <- setdiff(names(names_map), names(table))
  if (length(missing)) stop(sprintf("%s: missing columns %s; the file does not follow the expected layout",
                                    file_name, py_list(missing)), call. = FALSE)
  names(table) <- unname(names_map[names(table)])
  table
}

# One row per loan and period: the twelve loan-level files put together, sorted by loan, then period.
loan_performance <- function() {
  cached("loan_performance", function() {
    rows <- loan_level_all()[, PERFORMANCE_COLUMNS]
    rows <- rows[order(rows$loan_id, rows$period, method = "radix"), ]
    rownames(rows) <- NULL
    rows
  })
}

# Every loan of the pool at the end of the last period: its fixed fields and its latest status.
loan_snapshot <- function() {
  cached("loan_snapshot", function() {
    rows <- loan_level_all()
    last <- rows[!duplicated(rows$loan_id, fromLast = TRUE), ]
    snap <- rows[!duplicated(rows$loan_id), STATIC_COLUMNS]
    i <- match(snap$loan_id, last$loan_id)
    snap$status <- last$status[i]
    snap$current_balance <- last$closing_balance[i]
    snap$instalments_in_arrears <- last$instalments_in_arrears[i]
    snap$status_period <- last$period[i]
    rownames(snap) <- NULL
    snap
  })
}
