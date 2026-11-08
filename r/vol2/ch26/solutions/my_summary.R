# Reference answer to the practical task of chapter 26 (assessment question 10).
analyser_summary <- function(pdf) {
  terms <- extract_deal_terms(pdf, "rules")
  analysis <- analyse_deal_terms(terms)
  ce <- analysis$credit_enhancement
  list(fields_found = terms$coverage$found,
       class_a_ce = if (length(ce)) ce[[1]]$credit_enhancement else NA_real_,
       checks_passed = analysis$checks_passed)
}
