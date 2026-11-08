# Exercise 26.4: a new rule for Severn's servicer, which the prospectus calls the "Mortgage Administrator".
#   Rscript r/vol2/ch26/solutions/ex_26_4_servicer_rule.R
suppressMessages({ source("r/taragent/load_analyser.R"); source("r/vol2/ch26/analyser_logic.R") })

servicer_rule <- function(pdf) {
  pages <- page_texts(pdf)
  for (i in seq_along(pages)) {
    m <- regmatches(pages[i], regexec("Mortgage Administrator (.+?(?:Building Society|Limited|plc|Bank))", pages[i], perl = TRUE))[[1]]
    if (length(m)) return(list(value = m[2], page = i, quote = m[1], source = "rules"))
  }
  NULL
}

pdf <- sample_path("severn", "pdf")
terms <- extract_deal_terms(pdf, "rules")
found <- servicer_rule(pdf)
cat("Rule found:", found$value, "on page", found$page, "\n")
terms$parties$servicer <- found
terms <- ground_terms(terms, pdf)$terms                  # the new value goes through the same check
cat("Grounded:", terms$parties$servicer$grounded, "\n")
terms$coverage <- coverage(terms)
cat(sprintf("Fields found: %d of %d (was 5)\n", terms$coverage$found, terms$coverage$schema_fields))
