# Chapter 18: NULL in R, None in Python — the first breach before period 10 and up to period 12.
source("r/taragent/load.R")

before <- first_breach_period(up_to = 9)
cat("First breach in periods 1-9: ", if (is.null(before)) "none (NULL)" else before, "\n", sep = "")
cat("First breach in periods 1-12: ", first_breach_period(), "\n", sep = "")
cat("As JSON for the model: ", to_json(list(first_breach_period = before)), "\n", sep = "")
