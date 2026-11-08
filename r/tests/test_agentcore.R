# Tests for the shared R agent loop and the brains.
library(testthat)
# `root` (the repository folder) comes from helper-root.R.
source(file.path(root, "r", "agentcore", "loop.R"))
source(file.path(root, "r", "agentcore", "brains.R"))

schemas <- list(list(type = "function", `function` = list(
  name = "add", description = "Add two numbers.",
  parameters = list(type = "object",
                    properties = list(a = list(type = "number"), b = list(type = "number")),
                    required = list("a", "b")))))

call_tool <- function(name, args) {
  if (name != "add") return(to_json(list(error = paste0("unknown tool '", name, "'"))))
  to_json(list(result = args$a + args$b))
}

adding_rules <- function(memory) {
  last <- memory[[length(memory)]]
  if (last$role == "user") {
    return(list(content = "", tool_calls = list(list(name = "add", arguments = list(a = 2, b = 3)))))
  }
  list(content = sprintf("The total is %s.", fromJSON(last$content)$result), tool_calls = list())
}

quiet <- function(msg) invisible(NULL)

test_that("the loop runs a tool then answers", {
  out <- run_agent("Add 2 and 3.", rule_brain(adding_rules), schemas, call_tool, "You add numbers.", log = quiet)
  expect_equal(out$answer, "The total is 5.")
  expect_equal(vapply(out$steps, `[[`, "", "type"), c("tool", "answer"))
  expect_equal(vapply(out$memory, `[[`, "", "role"), c("system", "user", "assistant", "tool", "assistant"))
})

test_that("the step limit stops a brain that never answers", {
  forever <- rule_brain(function(m) list(content = "", tool_calls = list(list(name = "add", arguments = list(a = 1, b = 1)))))
  out <- run_agent("Add.", forever, schemas, call_tool, "", max_steps = 3, log = quiet)
  expect_equal(out$stopped_because, "step limit")
  expect_null(out$answer)
})

test_that("record then replay gives identical runs", {
  path <- tempfile(fileext = ".jsonl")
  first <- run_agent("Add 2 and 3.", recording_brain(rule_brain(adding_rules), path), schemas, call_tool, "", log = quiet)
  second <- run_agent("Add 2 and 3.", replay_brain(path), schemas, call_tool, "", log = quiet)
  # JSON stores 2 as a whole number, so R reads it back as an integer: equal in value, not in type.
  expect_equal(first$memory, second$memory)
})

test_that("a recording made in Python replays in R", {
  path <- tempfile(fileext = ".jsonl")
  writeLines(c('{"content": "", "tool_calls": [{"name": "add", "arguments": {"a": 2, "b": 3}}]}',
               '{"content": "The total is 5.", "tool_calls": []}'), path)
  out <- run_agent("Add 2 and 3.", replay_brain(path), schemas, call_tool, "", log = quiet)
  expect_equal(out$answer, "The total is 5.")
})

test_that("ollama_brain speaks the Ollama HTTP format", {
  script <- tempfile(fileext = ".json")
  writeLines('[{"content": "", "tool_calls": [{"name": "add", "arguments": {"a": 2, "b": 3}}]},
               {"content": "The total is 5.", "tool_calls": []}]', script)
  url_file <- tempfile(fileext = ".txt")
  system2("python3", c(file.path(root, "r", "tests", "helpers", "fake_ollama_server.py"), script, url_file), wait = FALSE)
  for (i in 1:100) { if (file.exists(url_file) && length(readLines(url_file, warn = FALSE)) > 0) break; Sys.sleep(0.1) }
  url <- readLines(url_file, warn = FALSE)
  out <- run_agent("Add 2 and 3.", ollama_brain(host = url), schemas, call_tool, "You add numbers.", log = quiet)
  expect_equal(out$answer, "The total is 5.")
  received_file <- paste0(url_file, ".received.json")
  for (i in 1:50) { if (file.exists(received_file)) break; Sys.sleep(0.1) }
  received <- fromJSON(received_file, simplifyVector = FALSE)
  expect_equal(received[[1]]$model, "qwen2.5:7b")
  expect_equal(received[[1]]$options, list(temperature = 0L, seed = 42L, num_ctx = 8192L))
  expect_equal(received[[1]]$tools[[1]]$`function`$name, "add")
  last <- received[[2]]$messages[[4]]
  expect_equal(last$role, "tool")
  expect_equal(last$tool_name, "add")
})

test_that("a failed recording leaves no file", {
  path <- tempfile(fileext = ".jsonl")
  broken <- list(next_step = function(memory, schemas) stop("Ollama is not running"))
  brain <- recording_brain(broken, path)
  expect_error(brain$next_step(list(), list()), "Ollama")
  expect_false(file.exists(path))
  expect_false(file.exists(paste0(path, ".partial")))
})

test_that("an empty recording counts as missing", {
  path <- tempfile(fileext = ".jsonl")
  file.create(path)
  expect_false(recording_ready(path))
  expect_error(replay_brain(path), "no recording")
})
