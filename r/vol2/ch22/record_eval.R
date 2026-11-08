# Chapter 22: score the live model on the 40 questions from R (record) or replay the recorded run.
#   Rscript r/vol2/ch22/record_eval.R record       record with Ollama: one recording per question
#   Rscript r/vol2/ch22/record_eval.R     score the recorded replies
source("r/taragent/load.R")

args <- commandArgs(trailingOnly = TRUE)
mode <- if (length(args) > 0) args[1] else "replay"     # record only when asked: "record"
if (mode == "replay" && !(file.exists(file.path(EVAL_RECORDINGS, "Q01.jsonl")) && file.size(file.path(EVAL_RECORDINGS, "Q01.jsonl")) > 0)) {
  cat("[Recording pending: run python record_all.py with Ollama installed, then rebuild]\n")
} else {
  out <- run_evaluation(mode)
  for (r in out$results) if (!r$correct) cat(sprintf("%s  WRONG  %s\n", r$id, r$reason))
  cat(sprintf("Score (qwen2.5:7b from R, %s): %d / %d\n", mode, as.integer(out$score), out$out_of))
}
