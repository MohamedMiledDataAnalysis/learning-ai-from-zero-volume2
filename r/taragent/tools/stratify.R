# Tool 2 — pool stratifications (R version of tar_agent/tools/stratify.py).
#
# Splits the pool into groups (region, product, credit score band...) at the cut-off
# date or at the end of any period, and totals a measure in each group.

# Bands match the tables in section 3 of the prospectus: (column, edges, labels).
BANDS <- list(
  credit_score_band = list("credit_score", c(-1, 649, 699, 749, 799, 849, 999),   # -1: a score of 0 is valid
                           c("Below 650", "650-699", "700-749", "750-799", "800-849", "850 and above")),
  interest_rate_band = list("interest_rate_pct", c(0, 7.99, 8.99, 9.99, 10.99, 99),
                            c("Below 8.00%", "8.00-8.99%", "9.00-9.99%", "10.00-10.99%", "11.00% and above")),
  ltv_band = list("ltv_original_pct", c(0, 79.99, 84.99, 89.99, 94.99, 100),
                  c("Below 80%", "80-84.99%", "85-89.99%", "90-94.99%", "95-100%"))
)
FIELDS <- c("region", "product", "vehicle_type", "fuel_type", "employment_status", names(BANDS))
MEASURES <- c("balance", "count", "balance_90plus")

# The live loans with their balances: at the cut-off date (period 0) or at the end of a period.
pool_at <- function(period) {
  tape <- load_clean_tape()
  if (period == 0) {
    pool <- tape
    pool$balance <- tape$current_balance
    pool$instalments_in_arrears <- 0
  } else {
    check_period(period)
    perf <- loan_performance()
    p <- perf[perf$period == period & perf$status %in% c("Current", "Arrears"),
              c("loan_id", "closing_balance", "instalments_in_arrears")]
    pool <- merge(tape, p, by = "loan_id", sort = FALSE)
    names(pool)[names(pool) == "closing_balance"] <- "balance"
  }
  for (name in names(BANDS)) {
    b <- BANDS[[name]]
    # cut() puts each value in the band (lower edge, upper edge]; a missing value goes in "Missing".
    band <- as.character(cut(pool[[b[[1]]]], breaks = b[[2]], labels = b[[3]], right = TRUE))
    band[is.na(band)] <- "Missing"
    pool[[name]] <- factor(band, levels = c(b[[3]], "Missing"))
  }
  pool
}

# Tool entry point.
#   by      one of FIELDS
#   period  0 for the cut-off date, 1 to 12 for the end of a collection period
#   measure "balance", "count" or "balance_90plus"
stratify_pool <- function(by, period = 0, measure = "balance") {
  if (!(by %in% FIELDS)) stop(paste0("'by' must be one of ", py_list(FIELDS)), call. = FALSE)
  if (!(measure %in% MEASURES)) stop(paste0("'measure' must be one of ", py_list(MEASURES)), call. = FALSE)
  pool <- pool_at(period)
  pool$value <- switch(measure,
                       balance = pool$balance,
                       count = rep(1, nrow(pool)),
                       balance_90plus = ifelse(pool$instalments_in_arrears >= 3, pool$balance, 0))
  # Groups in the same order as pandas: band order for bands, alphabetical (by character code) otherwise.
  key <- pool[[by]]
  groups <- if (is.factor(key)) levels(droplevels(key)) else sort(unique(key), method = "radix")
  value <- vapply(groups, function(g) sum(pool$value[key == g]), numeric(1), USE.NAMES = FALSE)
  group_balance <- vapply(groups, function(g) sum(pool$balance[key == g]), numeric(1), USE.NAMES = FALSE)
  total <- sum(value)
  rows <- list()
  for (k in order(-value)) {                       # largest first; order() keeps ties in group order
    row <- list(group = groups[k])
    row[[measure]] <- round(value[k], 2)
    row$share_of_total <- if (total != 0) round(value[k] / total, 6) else 0
    if (measure == "balance_90plus") {
      # How much of the group's own balance is 90+ in arrears: shows concentration.
      row$ratio_within_group <- if (group_balance[k] != 0) round(value[k] / group_balance[k], 6) else 0
    }
    rows[[length(rows) + 1]] <- row
  }
  list(period = period, by = by, measure = measure, total = round(total, 2),
       loans_in_pool = nrow(pool), rows = rows)
}
