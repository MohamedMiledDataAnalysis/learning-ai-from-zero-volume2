# Chapter 20: a recording written in Python's format, replayed by the R agent.
source("r/taragent/load.R")

recording <- tempfile(fileext = ".jsonl")
writeLines(c(
  '{"content": "", "tool_calls": [{"name": "run_trigger_tests", "arguments": {"period": 10}}]}',
  '{"content": "In period 10 the 90+ day arrears ratio is 1.32%, above the 1.25% limit.", "tool_calls": []}'),
  recording)
run <- ask("What is the 90+ day arrears ratio in period 10?", "replay", recording)
cat("\nAnswer:", run$answer, "\n")
unlink(recording)
