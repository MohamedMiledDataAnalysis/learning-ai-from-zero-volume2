# Tool 1 — load and validate the loan tape (R version of tar_agent/tools/loan_tape.py).
#
# The same nine rules, in the same order, with the same suggested fixes. A rule never
# guesses: when the correct value cannot be known, the value is set to missing and flagged.

REQUIRED <- c("loan_id", "origination_date", "maturity_date", "original_balance", "current_balance",
              "interest_rate_pct", "credit_score", "region", "postcode_area")

POOL_CUT <- file.path(DATA_DIR, "originator", "THAMES_2026-1_AUTL_Pool_Cut_2025-12-31.csv")
SUPPLEMENTARY <- file.path(DATA_DIR, "originator", "Kestrel_Thames_2026-1_Supplementary_Data_2025-12-31.csv")
DICTIONARY <- file.path(DATA_DIR, "originator", "Kestrel_Thames_2026-1_Data_Dictionary.xlsx")

# The working name of each column, and where it comes from: a field of the FCA template, or a field of the
# supplementary file. Columns marked "code" hold a list code that the dictionary's "List Codes" sheet decodes.
TAPE_SOURCES <- list(
  c("loan_id", "AUTL2", "text"), c("origination_date", "AUTL24", "text"), c("maturity_date", "AUTL25", "text"),
  c("original_term_months", "AUTL26", "integer"), c("remaining_term_months", NA, "integer"),
  c("product", "AUTL23", "code"), c("vehicle_type", "AUTL56", "code"), c("fuel_type", "Fuel Type", "text"),
  c("vehicle_value", "AUTL60", "number"), c("original_balance", "AUTL29", "number"),
  c("current_balance", "AUTL30", "number"), c("balloon_amount", "AUTL38", "number"),
  c("ltv_original_pct", "AUTL59", "number"), c("interest_rate_pct", "AUTL40", "number"),
  c("monthly_instalment", "AUTL37", "number"), c("credit_score", "Bureau Score at Origination", "integer"),
  c("employment_status", "AUTL12", "code"), c("annual_income", "AUTL16", "number"), c("region", "Region", "text"),
  c("postcode_area", "Postcode Area", "text"), c("days_past_due", "AUTL69", "integer"))

# One sheet of the originator's data dictionary.
read_dictionary <- function(sheet, path = DICTIONARY) {
  as.data.frame(readxl::read_excel(path, sheet = sheet, col_types = "text"))
}

read_text_csv <- function(path) {
  read.csv(path, colClasses = "character", na.strings = character(0), check.names = FALSE)
}

# Read the cut-off tape exactly as received, with working column names. The tape is the FCA template file
# (fields AUTL1 to AUTL84), with the supplementary file joined on AUTL2; list codes become the originator's
# own values through the dictionary. An empty cell stays "". A CSV in working names is read as it is.
read_tape <- function(path = NULL, supplementary = NULL) {
  if (is.null(path)) path <- POOL_CUT
  tape <- read_text_csv(path)
  if ("loan_id" %in% names(tape)) return(read.csv(path, stringsAsFactors = FALSE, na.strings = character(0)))
  codes <- read_dictionary("FCA Template AUTL")$`Field Code`
  if (!identical(names(tape), codes))
    stop(sprintf("%s does not follow the FCA template: expected the fields AUTL1 to AUTL84 in order",
                 basename(path)), call. = FALSE)
  extra <- read_text_csv(if (is.null(supplementary)) SUPPLEMENTARY else supplementary)
  i <- match(tape$AUTL2, extra$AUTL2)                        # duplicated rows stay duplicated
  for (f in setdiff(names(extra), "AUTL2")) tape[[f]] <- ifelse(is.na(i), "", extra[[f]][i])
  lists <- read_dictionary("List Codes")
  decode <- setNames(lists$`Kestrel Value`, paste(lists$`Field Code`, lists$Code))
  out <- data.frame(row.names = seq_len(nrow(tape)))
  for (s in TAPE_SOURCES) {
    name <- s[1]; source <- s[2]; kind <- s[3]
    out[[name]] <- if (name == "remaining_term_months") as.integer(tape$AUTL26) - as.integer(tape$AUTL47) else
      switch(kind,
             code = unname(ifelse(is.na(decode[paste(source, tape[[source]])]), tape[[source]],
                                  decode[paste(source, tape[[source]])])),
             number = as.numeric(tape[[source]]),
             integer = as.integer(tape[[source]]),
             text = tape[[source]])
  }
  rownames(out) <- NULL
  out
}

# Python's str.title(): every word starts with a capital, the rest is lower case.
py_title <- function(s) {
  gsub("(^|[^A-Za-z])([a-z])", "\\1\\U\\2", tolower(s), perl = TRUE)
}

# The similarity score of Python's difflib.SequenceMatcher: 2 x (matching characters) / (total characters).
# Matching characters are found as in difflib: the longest common block, then the same on each side of it.
similarity <- function(a, b) {
  a <- strsplit(a, "")[[1]]
  b <- strsplit(b, "")[[1]]
  matched <- function(alo, ahi, blo, bhi) {
    best <- c(0, alo, blo)                     # size, start in a, start in b
    if (alo > ahi || blo > bhi) return(0)
    for (i in alo:ahi) for (j in blo:bhi) {
      k <- 0
      while (i + k <= ahi && j + k <= bhi && a[i + k] == b[j + k]) k <- k + 1
      if (k > best[1]) best <- c(k, i, j)
    }
    if (best[1] == 0) return(0)
    best[1] + matched(alo, best[2] - 1, blo, best[3] - 1) +
      matched(best[2] + best[1], ahi, best[3] + best[1], bhi)
  }
  2 * matched(1, length(a), 1, length(b)) / (length(a) + length(b))
}

# difflib.get_close_matches(word, choices, n = 1, cutoff = 0.8): the closest choice, or NULL.
closest_match <- function(word, choices, cutoff = 0.8) {
  scores <- vapply(choices, function(ch) similarity(word, ch), numeric(1))
  if (max(scores) < cutoff) return(NULL)
  best <- choices[scores == max(scores)]
  sort(best, method = "radix", decreasing = TRUE)[1]      # ties: difflib keeps the larger string
}

# Run every rule and return a list of issues (one list per problem), in the order Python finds them.
find_issues <- function(tape) {
  issues <- list()
  add <- function(row, column, value, rule, fix) {
    issues[[length(issues) + 1]] <<- list(loan_id = row$loan_id, column = column, value = value,
                                          rule = rule, fix = fix)
  }
  # Rule 1: a row that appears twice.
  dups <- tape[duplicated(tape), ]
  for (i in seq_len(nrow(dups))) add(dups[i, ], "(whole row)", "", "duplicate row", "drop the second copy")
  # Rule 2: the same loan_id on two different rows.
  unique_rows <- tape[!duplicated(tape), ]
  same_id <- unique_rows[duplicated(unique_rows$loan_id), ]
  for (i in seq_len(nrow(same_id))) {
    add(same_id[i, ], "loan_id", same_id$loan_id[i], "loan_id used by two different rows", "ask the originator")
  }
  for (i in seq_len(nrow(unique_rows))) {
    row <- unique_rows[i, ]
    # Rule 3: required fields must not be empty.
    for (col in REQUIRED) {
      if (trimws(as.character(row[[col]])) == "") add(row, col, "", "missing value", "leave missing and flag")
    }
    # Rule 4: balances must be positive and not above the amount lent.
    if (row$current_balance < 0) {
      add(row, "current_balance", row$current_balance, "negative balance", "take the absolute value")
    } else if (row$current_balance > row$original_balance) {
      add(row, "current_balance", row$current_balance, "balance above the amount lent", "ask the originator")
    }
    # Rule 5: interest rates between 0% and 30%.
    rate <- row$interest_rate_pct
    if (!(rate > 0 && rate <= 30)) {
      if (rate > 100 && rate <= 3000) {
        add(row, "interest_rate_pct", rate, "rate out of range (decimal point missing)", "divide by 100")
      } else {
        add(row, "interest_rate_pct", rate, "rate out of range", "ask the originator")
      }
    }
    # Rule 6: credit scores are on a 0-999 scale.
    if (!(row$credit_score >= 0 && row$credit_score <= 999)) {
      add(row, "credit_score", row$credit_score, "credit score outside 0-999", "set to missing and flag")
    }
    # Rule 7: a loan matures after it starts (dates written YYYY-MM-DD compare correctly as dates).
    if (as.Date(row$maturity_date) <= as.Date(row$origination_date)) {
      add(row, "origination_date/maturity_date", paste0(row$origination_date, "/", row$maturity_date),
          "maturity date not after origination date", "swap the two dates")
    }
    # Rule 8: regions must use the standard names.
    if (!(row$region %in% STANDARD_REGIONS)) {
      match <- closest_match(py_title(row$region), STANDARD_REGIONS)
      fix <- if (is.null(match)) "ask the originator" else paste0("replace with '", match, "'")
      add(row, "region", row$region, "region not a standard name", fix)
    }
    # Rule 9: eligibility criterion — no arrears at the cut-off date.
    if (row$days_past_due != 0) {
      add(row, "days_past_due", row$days_past_due, "loan in arrears at cut-off (not eligible)",
          "ask the originator")
    }
  }
  issues
}

# Apply the safe fixes. Issues whose fix is "ask the originator" are left unchanged.
clean_tape <- function(tape, issues) {
  out <- tape[!duplicated(tape), ]
  rownames(out) <- NULL
  out$credit_score <- as.integer(out$credit_score)
  for (issue in issues) {
    i <- which(out$loan_id == issue$loan_id)
    col <- issue$column
    fix <- issue$fix
    if (fix == "take the absolute value") {
      out[i, col] <- abs(out[i, col])
    } else if (fix == "divide by 100") {
      out[i, col] <- round(out[i, col] / 100, 2)
    } else if (fix == "set to missing and flag") {
      out[i, col] <- NA
    } else if (fix == "swap the two dates") {
      dates <- out[i, c("origination_date", "maturity_date")]
      out[i, "origination_date"] <- dates$maturity_date
      out[i, "maturity_date"] <- dates$origination_date
    } else if (startsWith(fix, "replace with")) {
      out[i, col] <- strsplit(fix, "'")[[1]][2]
    }
  }
  out
}

# Tool entry point. Returns a summary the model can read, without the 5,000 rows.
validate_loan_tape <- function(path = NULL, supplementary = NULL) {
  tape <- read_tape(path, supplementary)
  issues <- find_issues(tape)
  cleaned <- clean_tape(tape, issues)
  expected <- deal_terms()$initial_pool_balance
  total <- round(sum(cleaned$current_balance), 2)
  by_rule <- list()
  for (issue in issues) {
    by_rule[[issue$rule]] <- (if (is.null(by_rule[[issue$rule]])) 0 else by_rule[[issue$rule]]) + 1
  }
  list(
    rows_received = nrow(tape),
    loans_after_cleaning = nrow(cleaned),
    issues_found = length(issues),
    issues_by_rule = by_rule,
    issues = issues,
    balance_after_cleaning = total,
    initial_pool_balance_in_deal_terms = expected,
    reconciles = abs(total - expected) < 0.01
  )
}

# The cleaned cut-off tape, for the other tools (computed once per session).
load_clean_tape <- function(path = NULL, supplementary = NULL) {
  key <- paste0("clean_tape:", if (is.null(path)) "default" else path, ":", if (is.null(supplementary)) "" else supplementary)
  cached(key, function() {
    tape <- read_tape(path, supplementary)
    clean_tape(tape, find_issues(tape))
  })
}
