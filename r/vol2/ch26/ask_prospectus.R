# Chapter 26: ask a question about a prospectus, as the Ask tab does.
#   Rscript r/vol2/ch26/ask_prospectus.R --deal severn --mode rules
#   Rscript r/vol2/ch26/ask_prospectus.R --deal severn --mode record     # needs Ollama
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
args <- commandArgs(trailingOnly = TRUE)
opt <- function(name, default) { i <- match(paste0("--", name), args); if (is.na(i)) default else args[i + 1] }
deal <- opt("deal", "severn"); mode <- opt("mode", "rules")
question <- opt("question", "What is the limit of the arrears trigger?")
recording <- ask_recording(deal)
if (mode == "record" && !(identical(deal, ASK_RECORDED$sample) && identical(question, ASK_RECORDED$question))) {
  stop("record only the question the app replays: --deal severn and the default question")
}
if (mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) { cat(PENDING, "\n", sep = ""); quit(status = 0) }
res <- ask_document(sample_path(deal, "pdf"), question, mode, recording)
cat("Question:", question, "\n")
cat("Pages of the passages:", paste(vapply(res$passages, function(h) h$page, 1L), collapse = ", "), "\n")
cat(strwrap(paste("Answer:", res$answer), 78), sep = "\n")
