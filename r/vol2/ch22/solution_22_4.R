# Solution 22.4: how many of the 40 questions expect each tool, and of which kind is each expected answer?
source("r/taragent/load.R")

questions <- load_questions()
tools <- vapply(questions, function(q) q$tools[[1]], "")
kinds <- vapply(questions, function(q) q$expected$kind, "")
print(table(tool = tools, kind = kinds))
cat(sprintf("\nQuestions that must cite a page: %d\n", sum(vapply(questions, function(q) !is.null(q$expected$page), TRUE))))
