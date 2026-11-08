# Solution 22.6: are the R agent's 40 answers the same text as the Python agent's?
source("r/taragent/load.R")

python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
code <- paste0("import sys, json; sys.path.insert(0, 'python'); from tar_agent.agent import ask; ",
               "from tar_agent.evaluate import load_questions; ",
               "print(json.dumps([ask(q['question'], 'rules', None, log=lambda m: None)['answer'] for q in load_questions()]))")
py_answers <- fromJSON(paste(system2(python, c("-c", shQuote(code)), stdout = TRUE), collapse = ""))
questions <- load_questions()
r_answers <- vapply(questions, function(q) ask(q$question, log = function(m) invisible(NULL))$answer, "")
same <- r_answers == py_answers
cat(sprintf("Identical answers: %d of %d\n", sum(same), length(same)))
for (i in which(!same)) {
  cat(sprintf("\n%s %s\n  R : %s...\n  Py: %s...\n", questions[[i]]$id, questions[[i]]$question,
              substr(r_answers[i], 1, 100), substr(py_answers[i], 1, 100)))
}
