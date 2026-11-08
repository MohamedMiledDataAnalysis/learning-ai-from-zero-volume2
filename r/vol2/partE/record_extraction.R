# Run the model layer of the extraction on one of the book's prospectuses (R version).
#
#   Rscript r/vol2/partE/record_extraction.R --deal severn --mode replay
#   Rscript r/vol2/partE/record_extraction.R --deal severn --mode record    # needs Ollama
#
# Modes: simulated (a stand-in built from the answer key, labelled as such), replay, live, record.

source("r/taragent/load_analyser.R")
args <- commandArgs(trailingOnly = TRUE)
opt <- function(name, default) { i <- match(paste0("--", name), args); if (is.na(i)) default else args[i + 1] }
deal <- opt("deal", "severn")
mode <- opt("mode", "replay")
pdf <- file.path(repo_root(), "data", if (deal == "thames") "prospectus" else "prospectus_rmbs", "prospectus.pdf")
key <- fromJSON(file.path(repo_root(), "data", "schemas",
                          if (deal == "thames") "answers_thames.json" else "answers_rmbs.json"), simplifyVector = FALSE)
recording <- file.path(repo_root(), "r", "recordings", sprintf("vol2-partE-extract-%s.jsonl", deal))
if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) {
  cat("[Recording pending: run python record_all.py with Ollama installed, then rebuild]\n")
  quit(status = 0)
}
brain <- if (mode == "simulated") simulated_model_brain(key) else make_brain(mode, recording)
terms <- extract_deal_terms(pdf, layer = "both", brain = brain)
score <- score_against_key(terms, key)
label <- if (mode == "simulated") "simulated model (not a language model)" else sprintf("model, %s mode", mode)
cat(sprintf("Deal: %s   layers: rules + %s\n", deal, label))
cat(sprintf("Schema fields found: %d of %d\n", terms$coverage$found, terms$coverage$schema_fields))
cat(sprintf("Answer key: %d of %d values found, %d correct\n", score$found, score$fields, score$correct))
cat("Sections:", paste(vapply(terms$model_log, function(s) paste(s$section, if (s$ok) "ok" else "FAILED"), character(1)),
                       collapse = ", "), "\n")
cat("Values that failed the page grounding check:", if (length(terms$ungrounded)) paste(unlist(terms$ungrounded), collapse = ", ") else "none", "\n")
