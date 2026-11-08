# The command line for the R agent. Run from the repository root:
#
#   Rscript r/taragent/cli.R ask "Run the trigger tests for period 10." --mode rules
#   Rscript r/taragent/cli.R ask "..." --mode replay --recording r/recordings/x.jsonl --quiet
#   Rscript r/taragent/cli.R evaluate --mode rules
#   Rscript r/taragent/cli.R export --period 10 --out out
#   Rscript r/taragent/cli.R surveil --period 10 --approve        (or --no-approve; neither: asks)
#
# Modes: rules, live, record, replay (live and record need Ollama running).

source("r/taragent/load.R")

PENDING <- "[Recording pending: run python record_all.py with Ollama installed, then rebuild]"

# Read "--name value" and "--flag" options from the command line.
option <- function(args, name, default = NULL) {
  i <- match(paste0("--", name), args)
  if (is.na(i)) default else args[i + 1]
}
flag <- function(args, name) paste0("--", name) %in% args

# The period, required by export and surveil: stop with a clear message when it is missing.
period_option <- function(args) {
  value <- option(args, "period")
  if (is.null(value)) stop("--period is required: a whole number from 1 to 12, for example --period 10", call. = FALSE)
  p <- suppressWarnings(as.integer(value))
  if (is.na(p)) stop("--period must be a whole number from 1 to 12, not '", value, "'", call. = FALSE)
  p
}

main <- function(args) {
  command <- if (length(args) == 0) stop("usage: Rscript r/taragent/cli.R ask|evaluate|export|surveil [options]", call. = FALSE) else args[1]
  mode <- option(args, "mode", "rules")
  if (!(mode %in% c("rules", "live", "record", "replay"))) stop("--mode must be rules, live, record or replay", call. = FALSE)

  if (command == "ask") {
    recording <- option(args, "recording", file.path(RECORDINGS, "agent_question.jsonl"))
    if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) return(cat(PENDING, "\n", sep = ""))
    quiet <- flag(args, "quiet")
    out <- ask(args[2], mode, recording, log = if (quiet) function(m) invisible(NULL) else function(m) cat(m, "\n", sep = ""))
    cat("\nAnswer: ", out$answer, "\n", sep = "")
  } else if (command == "evaluate") {
    if (mode == "replay" && !dir.exists(EVAL_RECORDINGS)) return(cat(PENDING, "\n", sep = ""))
    out <- run_evaluation(mode)
    for (r in out$results) if (!r$correct) cat(sprintf("%s  WRONG  %s\n", r$id, r$reason))
    cat(sprintf("Score (%s mode): %d / %d\n", out$mode, as.integer(out$score), out$out_of))
    right <- sum(vapply(out$results, function(r) isTRUE(r$right_tools), logical(1)))
    cat(sprintf("Questions answered with the expected tools: %d / %d\n", right, out$out_of))
  } else if (command == "export") {
    path <- export_monthly_pack(period_option(args), option(args, "out", "out"))
    cat(sprintf("Wrote %s with sheets: %s\n", basename(path),
                paste(openxlsx::getSheetNames(path), collapse = ", ")))
  } else if (command == "surveil") {
    period <- period_option(args)
    approve <- if (flag(args, "approve")) TRUE else if (flag(args, "no-approve")) FALSE else NA
    plan <- option(args, "plan", "rules")
    brain <- NULL
    if (plan != "rules") {
      rec <- file.path(RECORDINGS, sprintf("agentic_plan_%02d.jsonl", period))
      if (plan == "replay" && !(file.exists(rec) && file.size(rec) > 0)) return(cat(PENDING, "\n", sep = ""))
      brain <- make_brain(plan, rec)
    }
    run_surveillance(period, plan, brain, option(args, "memory"), option(args, "out"), approve)
  } else {
    stop("command must be ask, evaluate, export or surveil", call. = FALSE)
  }
  invisible(NULL)
}

main(commandArgs(trailingOnly = TRUE))
