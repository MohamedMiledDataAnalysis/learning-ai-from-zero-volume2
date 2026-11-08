# Chapter 22: the R scorer on right and wrong answers.
source("r/taragent/load.R")

expected <- list(kind = "number", value = 1.25, tolerance = 0, page = 9)
for (answer in c("The limit is 1.25% (page 9).", "The limit is 1.25%.", "The limit is 1.5% (page 9).",
                 "The limit is 1.25% (page 8).")) {
  s <- score_answer(answer, expected)
  cat(sprintf("%-5s  %-32s %s\n", if (s$correct) "RIGHT" else "WRONG", answer, s$reason))
}
