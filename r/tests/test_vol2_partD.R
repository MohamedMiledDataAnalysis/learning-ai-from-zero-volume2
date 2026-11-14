# Tests for the R finance agent (Volume 2, Part D), including the cross-language checks:
# every tool must return the same figures in R as in Python.
library(testthat)
# `root` comes from helper-root.R.
old <- setwd(root)
source(file.path(root, "r", "taragent", "load.R"))
setwd(old)

python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
ref_file <- tempfile(fileext = ".json")
system2(python, file.path(root, "r", "tests", "helpers", "python_reference.py"), stdout = ref_file)
ref <- fromJSON(ref_file, simplifyVector = FALSE)
r_json <- function(x) fromJSON(to_json(x), simplifyVector = FALSE)     # the R result as the model sees it

# Two results agree when every number is equal to 1e-9 and every text is identical.
expect_same <- function(r, py) expect_equal(r, py, tolerance = 1e-9)

# ------------------------------------------------------------------ Tool 1
test_that("validation finds the same nine issues, in the same order, as Python", {
  expect_same(r_json(validate_loan_tape()), ref$validate)
})

test_that("difflib's similarity is reproduced: the lower-case region is matched", {
  expect_equal(py_title("yorkshire and the humber"), "Yorkshire And The Humber")
  expect_equal(closest_match("Nort West", STANDARD_REGIONS), "North West")
  expect_equal(round(similarity("Nort West", "North West"), 4), 0.9474)
})

# ------------------------------------------------------------------ Tool 2
test_that("every stratification equals Python's, group by group and in the same order", {
  for (key in names(ref$stratify)) {
    p <- strsplit(key, "|", fixed = TRUE)[[1]]
    r <- r_json(stratify_pool(p[1], as.integer(p[2]), p[3]))
    expect_same(r, ref$stratify[[key]])
  }
})

# ------------------------------------------------------------------ Tool 3
test_that("the trigger tests equal Python's in all 12 periods", {
  for (period in 1:12) expect_same(r_json(run_trigger_tests(period)), ref$triggers[[as.character(period)]])
  expect_equal(first_breach_period(), 10)
})

# ------------------------------------------------------------------ Tool 4
test_that("prospectus search: same pages and sections; scores differ only through the PDF text", {
  # pdftools keeps words whole ("Total") where pypdf splits a few ("T otal"), so word counts,
  # and therefore BM25 scores, differ slightly. Pages, sections and order agree for these queries.
  for (q in names(ref$search)) {
    r <- search_prospectus(q)$results
    py <- ref$search[[q]]
    # Only the top two are compared: on the 136-page prospectus the third result can come from a chunk
    # whose lines pdftools and pypdf break differently, and near-ties then swap.
    r <- r[1:2]
    py <- py[1:2]
    expect_equal(vapply(r, function(x) x$page, 0), vapply(py, function(x) x$page, 0), info = q)
    expect_equal(vapply(r, function(x) x$section, ""), vapply(py, function(x) x$section, ""), info = q)
    # Scores agree within 2%: the average chunk length differs a little between the two libraries (chapter 19).
    rs <- vapply(r, function(x) x$score, 0)
    ps <- vapply(py, function(x) x$score, 0)
    expect_true(all(abs(rs - ps) <= 0.02 * ps), info = q)
  }
})

test_that("the known limitation of keyword search is the same in R", {
  results <- search_prospectus("Which loans were eligible?")$results
  expect_equal(results[[1]]$page, 76)                    # Kestrel's dealer network wins on the word "eligible"
  expect_false(any(vapply(results, function(x) grepl("Each loan met the following criteria", x$text, fixed = TRUE), TRUE)))
})

# ------------------------------------------------------------------ Tool 5
test_that("the surveillance note is identical to Python's, character for character, in every period", {
  for (period in 1:12) expect_identical(draft_surveillance_note(period)$note_markdown, ref$notes[[as.character(period)]])
})

# ------------------------------------------------------------------ Registry
test_that("the model sees exactly the same tool schemas from R and from Python", {
  expect_same(r_json(tool_schemas()), ref$schemas)
})

test_that("bad calls return the same error messages as Python", {
  expect_equal(fromJSON(call_tool("run_trigger_test", list(period = 10)))$error, ref$errors$unknown_tool$error)
  expect_equal(fromJSON(call_tool("run_trigger_tests", list(month = 10)))$error, ref$errors$unknown_argument$error)
  expect_equal(fromJSON(call_tool("run_trigger_tests", list(period = 13)))$error, ref$errors$bad_period$error)
  expect_equal(fromJSON(call_tool("stratify_pool", list(by = "colour")))$error, ref$errors$bad_by$error)
  expect_match(fromJSON(call_tool("run_trigger_tests", "{period: 10}"))$error, "^arguments are not valid JSON")
})

# ------------------------------------------------------------------ Agent and evaluation
test_that("the R agent answers in rules mode with one tool call", {
  out <- ask("Run the trigger tests for period 10.", log = function(m) invisible(NULL))
  expect_equal(out$stopped_because, "final answer")
  expect_match(out$answer, "1.32% against a limit of 1.25% (breached)", fixed = TRUE)
  expect_equal(vapply(out$steps, function(s) s$type, ""), c("tool", "answer"))
})

test_that("the R rule brain scores 40 out of 40 with the expected tools", {
  out <- run_evaluation("rules")
  expect_equal(out$score, 40)
  expect_true(all(vapply(out$results, function(r) r$right_tools, TRUE)))
})

test_that("a Python recording replays in R", {
  rec <- tempfile(fileext = ".jsonl")
  writeLines(c('{"content": "", "tool_calls": [{"name": "run_trigger_tests", "arguments": {"period": 10}}]}',
               '{"content": "The 90+ day arrears ratio is 1.32% in period 10.", "tool_calls": []}'), rec)
  out <- ask("What is the 90+ day arrears ratio in period 10?", "replay", rec, log = function(m) invisible(NULL))
  expect_equal(out$answer, "The 90+ day arrears ratio is 1.32% in period 10.")
  expect_true(score_answer(out$answer, list(kind = "number", value = 1.321, tolerance = 0.006))$correct)
})

# ------------------------------------------------------------------ Packaging
test_that("the Excel pack has four sheets and the trigger values", {
  path <- export_monthly_pack(10, tempfile())
  expect_equal(openxlsx::getSheetNames(path), c("Summary", "Triggers", "Arrears by region", "Note"))
  trig <- openxlsx::read.xlsx(path, "Triggers")
  expect_equal(trig$Value, c(0.004477, 0.01321))
  expect_equal(openxlsx::read.xlsx(path, "Arrears by region")$Region[1], "North West")
})

# ------------------------------------------------------------------ Agentic
test_that("approval decides between outbox and drafts", {
  mem <- tempfile(); out <- tempfile(); quiet <- function(m) invisible(NULL)
  sent <- run_surveillance(9, memory_dir = mem, out_dir = out, approve = TRUE, log = quiet)
  held <- run_surveillance(10, memory_dir = mem, out_dir = out, approve = FALSE, log = quiet)
  expect_equal(sent$status, "sent")
  expect_true(file.exists(file.path(out, "outbox", "note_2026_09.md")))
  expect_equal(held$status, "held for approval")
  expect_true(file.exists(file.path(out, "drafts", "note_2026_10.md")))
  expect_match(held$changes[2], "Payment mode CHANGED from pro rata to sequential")
})

test_that("an incomplete plan from a brain is completed from the checklist", {
  brain <- rule_brain(function(memory) list(content = '[{"tool": "run_trigger_tests", "arguments": {"period": 10}, "why": "triggers"}]',
                                            tool_calls = list()))
  plan <- model_plan(brain, 10)
  checked <- check_plan(plan, 10)
  expect_length(plan, 1)
  expect_length(checked$missing, 3)
  expect_length(checked$plan, 4)
  expect_length(model_plan(rule_brain(function(m) list(content = "I would check the triggers.", tool_calls = list())), 10), 0)
})

test_that("a plan for another period is rejected and replanned exactly once", {
  wrong <- lapply(rule_plan(10), function(s) { s$arguments$period <- 9; s })
  replies <- c(as.character(to_json(wrong)), as.character(to_json(rule_plan(10))))
  calls <- character(0)
  brain <- rule_brain(function(memory) {
    calls <<- c(calls, memory[[1]]$content)
    list(content = replies[length(calls)], tool_calls = list())
  })
  r <- run_surveillance(10, plan_source = "model", brain = brain, memory_dir = tempfile(), out_dir = tempfile(),
                        approve = TRUE, log = function(m) invisible(NULL))
  expect_true(r$replanned)
  expect_length(calls, 2)
  expect_match(calls[2], "is for period 9, not period 10", fixed = TRUE)
  expect_equal(r$status, "sent")
})

test_that("a tool error holds the note instead of crashing", {
  results <- run_plan(rule_plan(10), log = function(m) invisible(NULL))
  results[[1]]$result <- list(error = "data file missing")
  check <- self_check(results, 10)
  expect_false(check$agree)
  expect_match(check$error, "missing or failed")
})

test_that("a failed self-check holds the note with the status held", {
  mem <- tempfile(); out <- tempfile()
  original <- self_check                      # the agent lives in the global environment: swap, then restore
  assign("self_check", function(results, period) list(figure = "x", trigger_tool = 0.01, recomputed = 0.02,
                                                      agree = FALSE), envir = globalenv())
  r <- tryCatch(run_surveillance(10, memory_dir = mem, out_dir = out, approve = TRUE,
                                 log = function(m) invisible(NULL)),
                finally = assign("self_check", original, envir = globalenv()))
  expect_equal(r$status, "held")
  expect_equal(r$reason, "the self-check disagrees")
  expect_false(dir.exists(file.path(out, "outbox")))
})

test_that("compare uses the latest earlier month in memory", {
  mem <- tempfile(); quiet <- function(m) invisible(NULL)
  run_surveillance(8, memory_dir = mem, out_dir = tempfile(), approve = TRUE, log = quiet)
  r <- run_surveillance(10, memory_dir = mem, out_dir = tempfile(), approve = TRUE, log = quiet)
  expect_match(r$changes[1], "since period 8 (0.96% to 1.32%).", fixed = TRUE)
})

test_that("Python and R share the same memory file", {
  mem <- tempfile(); quiet <- function(m) invisible(NULL)
  run_surveillance(9, memory_dir = mem, out_dir = tempfile(), approve = FALSE, log = quiet)
  code <- sprintf(paste0("import sys; sys.path.insert(0, %s); from tar_agent.agentic import load_memory;",
                         "m = load_memory(%s); print(m['9']['main_arrears_region'], m['9']['arrears_90_ratio'])"),
                  shQuote(normalizePath(file.path(root, "python"), winslash = "/", mustWork = FALSE)),
                  shQuote(normalizePath(mem, winslash = "/", mustWork = FALSE)))
  expect_equal(system2(python, c("-c", shQuote(code)), stdout = TRUE), "North West 0.011965")
})
