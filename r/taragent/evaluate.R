# The 40-question test set and the scorer (R version of tar_agent/evaluate.py).
#
# The questions and expected answers are the SAME file the Python agent uses:
# data/eval/questions.jsonl, computed once from the deal pack by Python. R reads it,
# asks its own agent each question, and scores the answers with the same rules.

QUESTIONS_FILE <- file.path(DATA_DIR, "eval", "questions.jsonl")
EVAL_RECORDINGS <- file.path(repo_root(), "r", "recordings", "eval")

load_questions <- function(path = QUESTIONS_FILE) {
  lines <- readLines(path, encoding = "UTF-8", warn = FALSE)
  lapply(lines[nchar(lines) > 0], fromJSON, simplifyVector = FALSE)
}

# Every number written in the answer: "£1,111,137.93" -> 1111137.93, "1.32%" -> 1.32.
numbers_in <- function(answer) {
  if (is.null(answer)) return(numeric(0))
  found <- regmatches(answer, gregexpr("[0-9][0-9,]*(?:\\.[0-9]+)?", answer, perl = TRUE))[[1]]
  as.numeric(gsub(",", "", found, fixed = TRUE))
}

# Return list(correct, reason).
score_answer <- function(answer, expected) {
  if (is.null(answer)) answer <- ""
  if (expected$kind == "number") {
    found <- numbers_in(answer)
    ok <- any(abs(found - expected$value) <= expected$tolerance)
    reason <- if (ok) "figure found" else sprintf("expected %s (± %s)", as.character(expected$value), as.character(expected$tolerance))
  } else {
    words <- unlist(expected$contains)
    missing <- words[!vapply(words, function(w) grepl(tolower(w), tolower(answer), fixed = TRUE), logical(1))]
    ok <- length(missing) == 0
    reason <- if (ok) "text found" else paste0("missing: ", py_list(missing))
  }
  if (ok && !is.null(expected$pattern) && !grepl(expected$pattern, answer, perl = TRUE, ignore.case = TRUE)) {
    ok <- FALSE
    reason <- sprintf("figure not in the expected phrase (%s)", expected$pattern)
  }
  if (ok && !is.null(expected$page) &&
      !grepl(paste0("\\bpage ", expected$page, "\\b"), answer, perl = TRUE, ignore.case = TRUE)) {
    ok <- FALSE
    reason <- sprintf("page %d not cited", as.integer(expected$page))
  }
  list(correct = ok, reason = reason)
}

# Run the whole test set. mode: rules, live, record or replay.
run_evaluation <- function(mode = "rules", questions = NULL) {
  if (is.null(questions)) questions <- load_questions()
  results <- list()
  for (q in questions) {
    recording <- file.path(EVAL_RECORDINGS, paste0(q$id, ".jsonl"))
    if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) {
      results[[length(results) + 1]] <- list(id = q$id, correct = FALSE, reason = "recording pending",
                                             tools_used = list())
      next
    }
    run <- ask(q$question, mode, recording, log = function(m) invisible(NULL))
    s <- score_answer(run$answer, q$expected)
    used <- unlist(lapply(Filter(function(st) st$type == "tool", run$steps), function(st) st$name))
    results[[length(results) + 1]] <- list(id = q$id, correct = s$correct, reason = s$reason,
                                           tools_used = as.list(used),
                                           right_tools = all(unlist(q$tools) %in% used),
                                           steps = length(run$steps))
  }
  score <- sum(vapply(results, function(r) r$correct, logical(1)))
  list(mode = mode, score = score, out_of = length(results), results = results)
}
