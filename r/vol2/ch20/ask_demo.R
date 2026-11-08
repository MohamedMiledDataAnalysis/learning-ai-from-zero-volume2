# Chapter 20: the R agent answers one question with the rule brain.
source("r/taragent/load.R")

run <- ask("Which region holds most of the 90+ day arrears in October 2026?", "rules")
cat("\nAnswer:", run$answer, "\n")
