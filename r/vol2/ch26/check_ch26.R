# Chapter 26, assessment question 10: check your analyser_summary() function.
#
#   Rscript r/vol2/ch26/check_ch26.R              # checks r/vol2/ch26/my_summary.R (your file)
#   Rscript r/vol2/ch26/check_ch26.R --solution   # checks the reference answer
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })
file <- if ("--solution" %in% commandArgs(TRUE)) "r/vol2/ch26/solutions/my_summary.R" else "r/vol2/ch26/my_summary.R"
if (!file.exists(file)) { cat("Write your function in", file, "first.\n"); quit(status = 0) }
source(file)
expected <- list(thames = list(fields_found = 16, class_a_ce = 0.15, checks_passed = 5),
                 severn = list(fields_found = 5, class_a_ce = NA_real_, checks_passed = 0))
score <- 0
for (deal in names(expected)) {
  got <- analyser_summary(sample_path(deal, "pdf"))
  for (k in names(expected[[deal]])) {
    e <- expected[[deal]][[k]]; g <- got[[k]]
    ok <- if (is.na(e)) length(g) == 1 && is.na(g) else isTRUE(all.equal(as.numeric(g), e, tolerance = 1e-6))
    score <- score + ok
    got_txt <- if (is.null(g)) "NULL (missing)" else format(g)
    cat(sprintf("%-4s %-7s %-14s expected %-6s got %s\n", if (ok) "PASS" else "FAIL", deal, k, format(e), got_txt))
  }
}
cat(sprintf("%d of 6 checks passed%s\n", score, if (score == 6) ": full mark." else "."))
