# Exercise 26.6: a sixth consistency check — every rated class has a rating, and only the last may be unrated.
#   Rscript r/vol2/ch26/solutions/ex_26_6_rating_check.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })

ratings_check <- function(analysis) {
  ce <- analysis$credit_enhancement
  if (!length(ce)) return(list(check = "classes are rated", passed = NA, detail = "no classes"))
  rated <- vapply(ce, function(r) !is.null(r$rating) && !is.na(r$rating) && nzchar(r$rating) &&
                                    !grepl("unrated|not rated", tolower(r$rating)), logical(1))
  ok <- all(rated[-length(rated)])                        # the most junior class may be unrated
  list(check = "classes are rated", passed = ok,
       detail = paste(vapply(ce, function(r) sprintf("%s %s", r$class, if (is.null(r$rating)) "—" else r$rating), ""),
                      collapse = ", "))
}

for (deal in c("thames", "severn")) {
  a <- analyse_deal_terms(run_extraction(sample_path(deal, "pdf"), "both", "simulated", deal)$terms)
  r <- ratings_check(a)
  cat(sprintf("%-7s %s: %s (%s)\n", deal, r$check, if (isTRUE(r$passed)) "pass" else "FAIL", r$detail))
}
