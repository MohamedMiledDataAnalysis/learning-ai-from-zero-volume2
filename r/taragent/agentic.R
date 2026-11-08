# From agent to agentic system (R version of tar_agent/agentic.py).
#
# Goal: "Keep Thames Auto Receivables 2026-1 under surveillance." Each month the system
#   1. PLANS the checks (rules or a model writes the plan),
#   2. CHECKS the plan: removes steps for another period or an unknown tool, adds any missing checklist step,
#   3. RUNS the plan with the five tools, and REPLANS once if the plan was unusable or a step failed,
#   4. SELF-CHECKS one figure by recomputing it with a second tool (a failure holds the note),
#   5. REMEMBERS the month's key figures and compares them with last month,
#   6. ASKS A HUMAN before sending the note (the one action that cannot be undone).

OUT_DIR <- file.path(repo_root(), "out")

# What an analyst checks every month. A plan missing any of these is completed before it runs.
CHECKLIST <- list(
  list(tool = "run_trigger_tests", why = "check the trigger tests and the payment mode"),
  list(tool = "stratify_pool", arguments = list(by = "region", measure = "balance_90plus"),
       why = "find where 90+ day arrears are concentrated"),
  list(tool = "stratify_pool", arguments = list(by = "region", measure = "balance"),
       why = "pool balance by region, for the self-check"),
  list(tool = "draft_surveillance_note", why = "draft the monthly note")
)

PLAN_PROMPT <- paste(
  "You plan the monthly surveillance of a securitisation. Available tools:",
  "validate_loan_tape, stratify_pool(by, period, measure), run_trigger_tests(period),",
  "search_prospectus(query), draft_surveillance_note(period).",
  "Reply with ONLY a JSON list of steps for period %d, each step like",
  "{\"tool\": \"...\", \"arguments\": {...}, \"why\": \"...\"}.", sep = "\n")

# --------------------------------------------------------------------------
# 1-2. Plan, and check the plan
# --------------------------------------------------------------------------

# The plan written by rules: the checklist itself, for this period.
rule_plan <- function(period) {
  lapply(CHECKLIST, function(s) {
    args <- if (is.null(s$arguments)) list() else s$arguments
    list(tool = s$tool, arguments = c(args, list(period = period)), why = s$why)
  })
}

# Ask a model for the plan. Returns a list of steps, or an empty list if the reply is not a JSON list.
# feedback: the problems found in the previous plan, sent back when the system replans.
model_plan <- function(brain, period, feedback = NULL) {
  prompt <- sprintf(PLAN_PROMPT, as.integer(period))
  if (length(feedback) > 0) {
    prompt <- paste0(prompt, "\nYour previous plan had these problems:\n", paste0("- ", feedback, collapse = "\n"))
  }
  reply <- brain$next_step(list(list(role = "user", content = prompt)), list())
  text <- if (is.null(reply$content)) "" else reply$content
  match <- regmatches(text, regexpr("(?s)\\[.*\\]", text, perl = TRUE))
  steps <- if (length(match) == 1) tryCatch(fromJSON(match, simplifyVector = FALSE), error = function(e) list()) else list()
  Filter(function(s) is.list(s) && !is.null(s$tool), steps)
}

# Is this step for the goal's period? (10 and 10L are the same period.)
same_period <- function(step, period) {
  p <- step$arguments$period
  is.numeric(p) && length(p) == 1 && p == period
}

# Does a plan step do what a checklist item asks, for the goal's period?
matches <- function(step, item, period) {
  if (!identical(step$tool, item$tool) || !same_period(step, period)) return(FALSE)
  for (k in names(item$arguments)) if (!identical(step$arguments[[k]], item$arguments[[k]])) return(FALSE)
  TRUE
}

# Return list(plan = completed plan, missing = missing checklist items, rejected = rejected steps with reasons).
# A step is rejected if its tool does not exist or it is for another period than the goal's.
check_plan <- function(plan, period) {
  kept <- list()
  rejected <- list()
  for (s in plan) {
    if (!(s$tool %in% names(TOOLS))) {
      rejected[[length(rejected) + 1]] <- list(step = s, reason = sprintf("unknown tool '%s'", s$tool))
    } else if ("period" %in% names(TOOLS[[s$tool]]$parameters$properties) && !same_period(s, period)) {
      p <- if (is.null(s$arguments$period)) "None" else format(s$arguments$period)
      rejected[[length(rejected) + 1]] <- list(step = s, reason = sprintf("%s is for period %s, not period %d",
                                                                        s$tool, p, as.integer(period)))
    } else {
      kept[[length(kept) + 1]] <- s
    }
  }
  missing <- Filter(function(item) !any(vapply(kept, matches, logical(1), item = item, period = period)), CHECKLIST)
  added <- lapply(missing, function(m) {
    args <- if (is.null(m$arguments)) list() else m$arguments
    list(tool = m$tool, arguments = c(args, list(period = period)), why = paste(m$why, "(added: missing from the plan)"))
  })
  list(plan = c(kept, added), missing = missing, rejected = rejected)
}

# --------------------------------------------------------------------------
# 3-5. Run, self-check, remember
# --------------------------------------------------------------------------

run_plan <- function(plan, log) {
  results <- list()
  for (i in seq_along(plan)) {
    step <- plan[[i]]
    args <- if (length(step$arguments) == 0) named_list() else step$arguments
    result <- fromJSON(call_tool(step$tool, args), simplifyVector = FALSE)
    log(sprintf("  step %d: %s(%s) — %s", i, step$tool, to_json(args), step$why))
    results[[length(results) + 1]] <- list(step = step, result = result)
  }
  results
}

# The first successful result of this tool with these arguments (results with an error are skipped).
find_result <- function(results, tool, ...) {
  wanted <- list(...)
  for (r in results) {
    if (r$step$tool == tool && is.null(r$result$error) &&
        all(vapply(names(wanted), function(k) isTRUE(all.equal(r$step$arguments[[k]], wanted[[k]])),
                   logical(1)))) return(r$result)
  }
  NULL
}

errors_in <- function(results) {
  failed <- Filter(function(r) !is.null(r$result$error), results)
  vapply(failed, function(r) sprintf("%s(%s) failed: %s", r$step$tool, to_json(r$step$arguments), r$result$error),
         character(1))
}

# Recompute the 90+ day arrears ratio from two stratifications and compare it with the trigger tool.
self_check <- function(results, period) {
  arrears <- find_result(results, "stratify_pool", measure = "balance_90plus", period = period)
  balance <- find_result(results, "stratify_pool", measure = "balance", period = period)
  trig <- find_result(results, "run_trigger_tests", period = period)
  if (is.null(arrears) || is.null(balance) || is.null(trig)) {
    return(list(figure = "90+ day arrears ratio", agree = FALSE,
                error = "a result needed for the self-check is missing or failed"))
  }
  value <- Filter(function(t) t$test == "arrears_90_ratio", trig$tests)[[1]]$value
  recomputed <- arrears$total / balance$total
  list(figure = "90+ day arrears ratio", trigger_tool = value, recomputed = round(recomputed, 6),
       agree = abs(recomputed - value) < 1e-6)
}

key_figures <- function(results, period) {
  trig <- find_result(results, "run_trigger_tests", period = period)
  tests <- setNames(lapply(trig$tests, function(t) t$value), vapply(trig$tests, function(t) t$test, ""))
  top <- find_result(results, "stratify_pool", measure = "balance_90plus", period = period)$rows[[1]]
  list(arrears_90_ratio = tests$arrears_90_ratio, cumulative_default_ratio = tests$cumulative_default_ratio,
       principal_payment_mode = trig$principal_payment_mode, main_arrears_region = top$group)
}

load_memory <- function(memory_dir) {
  path <- file.path(memory_dir, "surveillance_memory.json")
  if (file.exists(path)) fromJSON(path, simplifyVector = FALSE) else list()
}

# Saved with sorted keys and two-space indents, as Python does: either language can read it.
save_memory <- function(memory_dir, memory) {
  dir.create(memory_dir, recursive = TRUE, showWarnings = FALSE)
  memory <- memory[sort(names(memory), method = "radix")]
  memory <- lapply(memory, function(m) m[sort(names(m), method = "radix")])
  cat(as.character(toJSON(memory, auto_unbox = TRUE, pretty = 2, digits = NA)),      # ends with a newline; Python reads it the same
      file = file.path(memory_dir, "surveillance_memory.json"))
}

# The most recent month in memory before this period: list(period, figures), or NULL.
latest_before <- function(memory, period) {
  bad <- names(memory)[!grepl("^[0-9]+$", names(memory))]
  if (length(bad) > 0) stop(sprintf("memory key '%s' is not a period number: keys must be like \"9\"", bad[1]),
                            call. = FALSE)
  earlier <- sort(as.integer(names(memory))[as.integer(names(memory)) < period])
  if (length(earlier) == 0) return(NULL)
  last <- earlier[length(earlier)]
  list(period = last, figures = memory[[as.character(last)]])
}

compare <- function(previous, current, previous_period = NULL) {
  if (is.null(previous)) return("No earlier month in memory: this is the first month monitored.")
  d <- (current$arrears_90_ratio - previous$arrears_90_ratio) * 100
  since <- if (is.null(previous_period)) "the previous month" else sprintf("period %d", as.integer(previous_period))
  lines <- sprintf("90+ day arrears ratio moved by %+.2f points since %s (%.2f%% to %.2f%%).",
                   d, since, previous$arrears_90_ratio * 100, current$arrears_90_ratio * 100)
  if (previous$principal_payment_mode != current$principal_payment_mode) {
    lines <- c(lines, sprintf("Payment mode CHANGED from %s to %s.", previous$principal_payment_mode,
                              current$principal_payment_mode))
  }
  if (previous$main_arrears_region != current$main_arrears_region) {
    lines <- c(lines, sprintf("Main arrears region changed from %s to %s.", previous$main_arrears_region,
                              current$main_arrears_region))
  }
  lines
}

# --------------------------------------------------------------------------
# 6. The full cycle, with human approval
# --------------------------------------------------------------------------

ask_human <- function(note) {
  cat(note, "\n")
  answer <- if (interactive()) {
    readline("Send the note? (yes/no) ")          # the console or RStudio
  } else {
    cat("Send the note? (yes/no) ")               # Rscript: read one line typed in the terminal
    con <- file("stdin")
    on.exit(close(con))
    readLines(con, n = 1)
  }
  answer <- tolower(trimws(answer))
  length(answer) == 1 && answer %in% c("y", "yes")
}

# One monthly cycle. approve: TRUE, FALSE, or NA to ask the human.
run_surveillance <- function(period, plan_source = "rules", brain = NULL, memory_dir = NULL, out_dir = NULL,
                             approve = NA, log = function(m) cat(m, "\n", sep = "")) {
  check_period(period)
  if (is.null(memory_dir)) memory_dir <- file.path(DATA_DIR, "memory")
  if (is.null(out_dir)) out_dir <- OUT_DIR
  log(sprintf("Goal: keep the deal under surveillance — period %d", as.integer(period)))

  make_plan <- function(feedback = NULL) {
    raw <- if (plan_source == "rules") rule_plan(period) else model_plan(brain, period, feedback)
    checked <- check_plan(raw, period)
    log(sprintf("Plan: %d steps (%d added from the checklist, %d rejected)", length(checked$plan),
                length(checked$missing), length(checked$rejected)))
    checked$problems <- c(vapply(checked$rejected, function(r) r$reason, character(1)),
                          if (length(raw) == 0) "the plan was empty or not a JSON list" else character(0))
    checked
  }

  checked <- make_plan()
  replanned <- FALSE
  if (length(checked$problems) > 0 && plan_source != "rules") {   # the plan itself is unusable: replan first
    log(sprintf("Replanning once: %d problem(s) in the plan", length(checked$problems)))
    checked <- make_plan(checked$problems)
    replanned <- TRUE
  }
  results <- run_plan(checked$plan, log)
  if (length(errors_in(results)) > 0 && plan_source != "rules" && !replanned) {   # a step failed: replan once
    log(sprintf("Replanning once: %d step(s) failed", length(errors_in(results))))
    checked <- make_plan(errors_in(results))
    results <- run_plan(checked$plan, log)
    replanned <- TRUE
  }
  plan <- checked$plan

  check <- self_check(results, period)
  reason <- if (!is.null(check$error)) check$error else if (!check$agree) "the self-check disagrees" else NULL
  if (is.null(reason) && is.null(find_result(results, "draft_surveillance_note", period = period))) {
    reason <- "the note could not be drafted"
  }
  if (!is.null(reason)) {
    log(sprintf("Self-check: %s", reason))
  } else {
    log(sprintf("Self-check: 90+ ratio %.6f (trigger tool) vs %.6f (recomputed) — agree",
                check$trigger_tool, check$recomputed))
  }

  changes <- character(0)
  if (is.null(reason)) {                              # memory records computed figures, not sent notes
    memory <- load_memory(memory_dir)
    current <- key_figures(results, period)
    prev <- latest_before(memory, period)
    changes <- compare(prev$figures, current,
                       if (is.null(prev) || prev$period == period - 1) NULL else prev$period)
    memory[[as.character(period)]] <- current
    save_memory(memory_dir, memory)
    note <- find_result(results, "draft_surveillance_note", period = period)$note_markdown
    note <- paste0(note, "\n\n## Month on month\n", paste0("- ", changes, collapse = "\n"))
    note <- paste0(note, sprintf("\n\n## Self-check\n- 90+ day arrears ratio recomputed from two stratifications: %.4f%% — agrees with the trigger tool.",
                                 check$recomputed * 100))
    approved <- if (is.na(approve)) ask_human(note) else isTRUE(approve)
    status <- if (approved) "sent" else "held for approval"
  } else {                                            # a failure holds the note, whatever the approval
    note <- paste0(sprintf("# Note held — period %d\n\nReason: %s.\n\n", as.integer(period), reason),
                   paste0("- ", errors_in(results), collapse = "\n"))
    approved <- FALSE
    status <- "held"
  }
  folder <- file.path(out_dir, if (approved) "outbox" else "drafts")
  dir.create(folder, recursive = TRUE, showWarnings = FALSE)
  path <- file.path(folder, sprintf("note_2026_%02d.md", as.integer(period)))
  writeLines(note, path, useBytes = TRUE, sep = "")
  log(sprintf("Note %s: %s/%s", status, basename(folder), basename(path)))
  list(period = period, plan = plan, missing_from_plan = checked$missing, rejected_from_plan = checked$rejected,
       replanned = replanned, self_check = check, changes = changes, status = status, reason = reason,
       path = path, note = note)
}
