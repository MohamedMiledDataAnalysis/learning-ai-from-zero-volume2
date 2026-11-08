# Chapter 25: run the app's server tests and print one line per test (no browser needed).
results <- as.data.frame(testthat::test_file("r/tests/test_vol2_ch25_shiny.R", reporter = "silent"))
for (i in seq_len(nrow(results))) {
  cat(sprintf("%-4s %s\n", if (results$failed[i] == 0 && !results$error[i]) "PASS" else "FAIL", results$test[i]))
}
cat(sprintf("%d tests, %d failed\n", nrow(results), sum(results$failed > 0 | results$error)))
