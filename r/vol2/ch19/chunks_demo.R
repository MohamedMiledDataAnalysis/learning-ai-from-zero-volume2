# Chapter 19: how the prospectus is cut into chunks, in R.
source("r/taragent/load.R")

all_chunks <- chunks()
cat(sprintf("Pages: %d   Chunks: %d\n", max(vapply(all_chunks, function(c) c$page, 0)), length(all_chunks)))
example <- Filter(function(c) grepl("must not exceed 1.25%", c$text, fixed = TRUE), all_chunks)[[1]]
cat(sprintf("Example chunk (page %d, section '%s'):\n  %s\n", example$page, example$section, example$text))
cat("Its first 12 tokens:", head(example$tokens, 12), "\n")
cat("Tokens of the question:", tokens("What is the limit for the 90+ day arrears ratio?"), "\n")
