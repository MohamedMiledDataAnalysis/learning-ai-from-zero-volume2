# The structured finance agent in R: the five tools, the shared loop, and a brain.
# (R version of tar_agent/agent.py.)
#
# Run from the repository root:
#   Rscript r/taragent/cli.R ask "Run the trigger tests for period 10." --mode rules
#
# Modes: rules (finance_rules decides), live (Ollama), record (live + save), replay (play back).

SYSTEM_PROMPT <- paste(
  "You are a surveillance analyst's assistant for the securitisation Thames Auto Receivables 2026-1 plc.",
  "You answer questions about the deal using ONLY the tools provided. Rules:",
  "1. Every figure in your answer must come from a tool result. Never estimate or invent a figure.",
  "2. For questions about the deal's rules (limits, fees, definitions), call search_prospectus and cite the page as \"page N\".",
  "3. Periods are numbered 1 (January 2026) to 12 (December 2026). Period 0 means the cut-off date, 31 December 2025.",
  "4. Give percentages with two decimals (1.32%) and amounts in pounds with commas (£49,151,532.52).",
  "5. If a tool returns an error, read it, correct your call, and try again.",
  "6. Keep the final answer short: two to five sentences.", sep = "\n")

MONTHS <- c("january", "february", "march", "april", "may", "june", "july", "august",
            "september", "october", "november", "december")

# --------------------------------------------------------------------------
# Reading a question: which period does it mean?
# --------------------------------------------------------------------------

# Return the period a question refers to: 0 for the cut-off date, 1-12, or NULL.
find_period <- function(text) {
  t <- tolower(text)
  if (grepl("cut-off", t, fixed = TRUE) || grepl("cut off", t, fixed = TRUE)) return(0)
  m <- regmatches(t, regexec("period ([0-9]{1,2})", t))[[1]]
  if (length(m) == 2) return(as.integer(m[2]))
  for (i in seq_along(MONTHS)) if (grepl(paste0("\\b", MONTHS[i], "\\b"), t, perl = TRUE) && (MONTHS[i] != "may" || grepl("\\bMay\\b", text, perl = TRUE))) return(i)
  NULL
}

# --------------------------------------------------------------------------
# Formatting tool results as sentences
# --------------------------------------------------------------------------

money <- function(x) paste0("£", formatC(x, format = "f", digits = 2, big.mark = ","))
comma0 <- function(x) formatC(x, format = "f", digits = 0, big.mark = ",")

# Turn one tool result into the final answer sentence(s).
answer_from_result <- function(question, name, result) {
  if (!is.null(result$error)) return(sprintf("The tool %s returned an error: %s", name, result$error))
  if (name == "validate_loan_tape") {
    rules <- paste(sprintf("%s (%d)", names(result$issues_by_rule), unlist(result$issues_by_rule)), collapse = ", ")
    verdict <- if (result$reconciles) "reconciles" else "does NOT reconcile"
    return(sprintf(paste("The tape received has %s rows. Validation found %d issues: %s. After cleaning, %s loans",
                         "remain with a balance of %s, which %s with the initial pool balance of %s."),
                   comma0(result$rows_received), result$issues_found, rules, comma0(result$loans_after_cleaning),
                   money(result$balance_after_cleaning), verdict, money(result$initial_pool_balance_in_deal_terms)))
  }
  if (name == "run_trigger_tests") {
    tests <- setNames(result$tests, vapply(result$tests, function(t) t$test, ""))
    a <- tests$arrears_90_ratio
    c <- tests$cumulative_default_ratio
    first <- if (!is.null(result$first_breach_period)) {
      sprintf("The first trigger breach was in period %d.", as.integer(result$first_breach_period))
    } else "No trigger has been breached so far."
    pass <- function(t) if (t$breached) "breached" else "pass"
    return(sprintf(paste("In period %d, the 90+ day arrears ratio is %s against a limit of %s (%s), and the",
                         "cumulative default ratio is %s against a limit of %s (%s). Principal is paid %s. %s"),
                   as.integer(result$period), pct(a$value), pct(a$limit), pass(a), pct(c$value), pct(c$limit), pass(c),
                   if (result$principal_payment_mode == "sequential") "sequentially" else "pro rata", first))
  }
  if (name == "stratify_pool") {
    rows <- result$rows
    top <- rows[[1]]
    when <- if (result$period == 0) "at the cut-off date" else sprintf("at the end of period %d", as.integer(result$period))
    measure <- result$measure
    if (measure == "count") {
      return(sprintf("There are %s loans in the pool %s. The largest group is %s (%s loans).",
                     comma0(result$total), when, top$group, comma0(top$count)))
    }
    named <- Filter(function(r) grepl(tolower(r$group), tolower(question), fixed = TRUE), rows)
    wanted <- if (length(named) > 0) named[[1]] else top
    label <- if (measure == "balance_90plus") "90+ day arrears balance" else "balance"
    text <- sprintf("%s%s, %s holds %s of the %s, which is %s of the total of %s.",
                    toupper(substr(when, 1, 1)), substring(when, 2), wanted$group, money(wanted[[measure]]),
                    label, pct(wanted$share_of_total), money(result$total))
    if (identical(wanted, top)) return(paste(text, "It is the largest group."))
    return(sprintf("%s The largest group is %s with %s.", text, top$group, pct(top$share_of_total)))
  }
  if (name == "search_prospectus") {
    best <- result$results[[1]]
    return(sprintf("According to the prospectus (page %d, %s): \"%s\"", as.integer(best$page), best$section, best$text))
  }
  if (name == "draft_surveillance_note") return(result$note_markdown)
  to_json(result)
}

# --------------------------------------------------------------------------
# The rule brain for the finance agent
# --------------------------------------------------------------------------

has_any <- function(q, words) any(vapply(words, function(w) grepl(w, q, fixed = TRUE), logical(1)))

# Decide which tool answers a question, and with which arguments. Plain keyword rules.
choose_tool <- function(question) {
  q <- tolower(question)
  period <- find_period(question)
  or0 <- if (is.null(period)) 0 else period
  if (grepl("prospectus", q, fixed = TRUE)) return(list(name = "search_prospectus", arguments = list(query = question)))
  if (grepl("loan tape", q, fixed = TRUE)) return(list(name = "validate_loan_tape", arguments = named_list()))
  # Order matters: the stratification words are checked before "pool balance".
  if (has_any(q, c("region", "fuel", "pcp", "product", "how many loans"))) {
    by <- if (grepl("region", q, fixed = TRUE)) "region" else if (grepl("fuel", q, fixed = TRUE)) "fuel_type" else "product"
    measure <- if (grepl("how many loans", q, fixed = TRUE)) "count" else if (grepl("90+", q, fixed = TRUE)) "balance_90plus" else "balance"
    return(list(name = "stratify_pool", arguments = list(by = by, period = or0, measure = measure)))
  }
  if (has_any(q, c("note", "pool balance", "defaults", "prepayments"))) {
    return(list(name = "draft_surveillance_note", arguments = list(period = if (is.null(period)) NA else period)))
  }
  if (has_any(q, c("trigger", "arrears ratio", "default ratio", "breach", "pro rata", "sequential"))) {
    return(list(name = "run_trigger_tests", arguments = list(period = if (is.null(period) || period == 0) 12 else period)))
  }
  NULL
}

# Rule brain for the finance agent: one tool call, then an answer built from its result.
finance_rules <- function(memory) {
  question <- Filter(function(m) m$role == "user", memory)[[1]]$content
  last <- memory[[length(memory)]]
  if (last$role == "user") {
    choice <- choose_tool(question)
    if (is.null(choice)) {
      return(list(content = paste("I can only answer questions about the loan tape, the pool, the trigger tests,",
                                  "the prospectus and the monthly note."), tool_calls = list()))
    }
    return(list(content = "", tool_calls = list(choice)))
  }
  result <- fromJSON(last$content, simplifyVector = FALSE)
  list(content = answer_from_result(question, last$tool_name, result), tool_calls = list())
}

# --------------------------------------------------------------------------
# Running the agent
# --------------------------------------------------------------------------

RECORDINGS <- file.path(repo_root(), "r", "recordings")

# Ask the agent one question. Returns the run (answer, steps, memory).
ask <- function(question, mode = "rules", recording = file.path(RECORDINGS, "agent_question.jsonl"),
                log = function(m) cat(m, "\n", sep = ""), max_steps = 6) {
  brain <- make_brain(mode, recording, rules = finance_rules)
  run_agent(question, brain, tool_schemas(), call_tool, SYSTEM_PROMPT, max_steps = max_steps, log = log)
}
