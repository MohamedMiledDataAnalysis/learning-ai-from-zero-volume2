# Chapter 24: record (or replay) a live model writing the monthly plan from R, then check it.
#   Rscript r/vol2/ch24/record_plan.R record       record with Ollama
#   Rscript r/vol2/ch24/record_plan.R     replay the recording
source("r/taragent/load.R")

args <- commandArgs(trailingOnly = TRUE)
mode <- if (length(args) > 0) args[1] else "replay"     # record only when asked: "record"
recording <- file.path(RECORDINGS, "vol2_ch24_plan.jsonl")
if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) {
  cat("[Recording pending: run python record_all.py with Ollama installed, then rebuild]\n")
} else {
  folder <- tempfile()
  r <- run_surveillance(10, plan_source = "model", brain = make_brain(mode, recording),
                        memory_dir = file.path(folder, "m"), out_dir = file.path(folder, "o"), approve = FALSE)
  missing <- vapply(r$missing_from_plan, function(m) m$tool, "")
  cat("Steps missing from the model's plan:", if (length(missing) == 0) "none" else paste(missing, collapse = ", "), "\n")
}
