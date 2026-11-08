# Chapter 16: how rule 8 finds the closest region name (R's copy of Python's difflib).
source("r/taragent/load.R")

word <- py_title("yorkshire and the humber")
cat("Title case:", word, "\n\n")
scores <- vapply(STANDARD_REGIONS, function(r) similarity(word, r), numeric(1))
for (r in names(sort(scores, decreasing = TRUE))[1:3]) cat(sprintf("  %-26s %.4f\n", r, scores[[r]]))
cat("\nClosest match (cut-off 0.8):", closest_match(word, STANDARD_REGIONS), "\n")
cat("Closest match for 'Nort West':", closest_match("Nort West", STANDARD_REGIONS), "\n")
cat("Closest match for 'Midlands':", if (is.null(closest_match("Midlands", STANDARD_REGIONS))) "none (ask the originator)", "\n")
