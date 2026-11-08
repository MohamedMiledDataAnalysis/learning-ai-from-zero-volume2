# Chapter 20: record (or replay) the live model answering one question from R.
#   Rscript r/vol2/ch20/record_question.R record       record with Ollama (used by record_all.py)
#   Rscript r/vol2/ch20/record_question.R     replay the recording (used by the book)
source("r/taragent/load.R")

QUESTION <- "Which region holds most of the 90+ day arrears in October 2026, and is any trigger breached?"
args <- commandArgs(trailingOnly = TRUE)
mode <- if (length(args) > 0) args[1] else "replay"     # record only when asked: "record"
recording <- file.path(RECORDINGS, "vol2_ch20_question.jsonl")
if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) {
  cat("[Recording pending: run python record_all.py with Ollama installed, then rebuild]\n")
} else {
  run <- ask(QUESTION, mode, recording)
  cat("\nAnswer:", run$answer, "\n")
}
