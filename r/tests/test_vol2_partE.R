# Tests for the R Prospectus Analyser tools (Volume 2 Part E), including the cross-language
# checks: in rules mode and with the simulated model, R must return exactly Python's JSON.
library(testthat)
old <- setwd(root)
source(file.path(root, "r", "taragent", "load_analyser.R"))
setwd(old)

THAMES <- file.path(root, "data", "prospectus", "prospectus.pdf")
SEVERN <- file.path(root, "data", "prospectus_rmbs", "prospectus.pdf")
KEY_T <- fromJSON(file.path(root, "data", "schemas", "answers_thames.json"), simplifyVector = FALSE)
KEY_S <- fromJSON(file.path(root, "data", "schemas", "answers_rmbs.json"), simplifyVector = FALSE)

python <- if (nzchar(Sys.which("python3"))) Sys.which("python3") else Sys.which("python")
ref_file <- tempfile(fileext = ".json")
system2(python, file.path(root, "r", "tests", "helpers", "python_extract.py"), stdout = ref_file)
ref <- fromJSON(ref_file, simplifyVector = FALSE)
r_json <- function(x) fromJSON(to_json(x), simplifyVector = FALSE)

test_that("normalise_line joins split capitals but never class letters", {
  expect_equal(normalise_line("T est 2 — 90+ day  arrears ,  ( pro rata)"), "Test 2 — 90+ day arrears, (pro rata)")
  expect_equal(normalise_line("Class B interest"), "Class B interest")
})

test_that("headers and page numbers are removed from the Severn pages", {
  pages <- read_pages(SEVERN)
  expect_equal(length(pages), 13)
  expect_false(any(grepl("Offering circular", unlist(pages[-1]), fixed = TRUE)))
})

test_that("the rules find every Thames term and only part of Severn", {
  t <- extract_deal_terms(THAMES)
  expect_equal(t$coverage$found, 16)
  s <- score_against_key(t, KEY_T)
  expect_equal(c(s$fields, s$found, s$correct), c(50, 50, 50))
  v <- extract_deal_terms(SEVERN)
  expect_equal(v$coverage$found, 5)
  s <- score_against_key(v, KEY_S)
  expect_equal(c(s$fields, s$found, s$correct), c(76, 5, 5))
  expect_true(is_missing(v$parties$servicer$value))
})

test_that("the simulated model fills the schema and the grounding check catches a planted value", {
  m <- extract_deal_terms(SEVERN, "both", simulated_model_brain(KEY_S))
  s <- score_against_key(m, KEY_S)
  expect_equal(c(s$found, s$correct), c(76, 76))
  expect_equal(m$parties$issuer$source, "rules")
  expect_equal(m$parties$servicer$source, "model")
  pl <- extract_deal_terms(SEVERN, "model", simulated_model_brain(KEY_S, plant = list("classes.B.margin" = 0.018)))
  expect_equal(unlist(pl$ungrounded), "classes[1].margin")
})

test_that("an invalid reply is retried once, then the section is reported as failed", {
  bad <- rule_brain(function(memory) list(content = "{}", tool_calls = list()))
  t <- extract_model(THAMES, bad)
  expect_true(all(!vapply(t$model_log, function(x) x$ok, logical(1))))
  expect_equal(coverage(t)$found, 0)
  expect_error(extract_deal_terms(THAMES, "model"), "needs a brain")
})

test_that("analysis: credit enhancement and checks", {
  a <- analyse_deal_terms(extract_deal_terms(THAMES))
  ce <- setNames(vapply(a$credit_enhancement, function(r) r$credit_enhancement, numeric(1)),
                 vapply(a$credit_enhancement, function(r) r$class, character(1)))
  expect_equal(ce, c(A = 0.15, B = 0.09, C = 0.04, D = 0))
  expect_equal(c(a$checks_passed, a$checks_failed, a$checks_not_possible), c(5, 0, 0))
  v <- analyse_deal_terms(extract_deal_terms(SEVERN))
  expect_equal(v$checks_not_possible, 5)
  s <- analyse_deal_terms(extract_deal_terms(SEVERN, "both", simulated_model_brain(KEY_S)))
  z <- s$credit_enhancement[[5]]
  expect_equal(c(z$reserve_support, z$credit_enhancement), c(0, 0))      # the GRF does not cover Class Z
  expect_false(value_on_page(0.025, "the notes below Class A represent 12.50 per cent"))
})

test_that("R and Python return the same JSON for both prospectuses", {
  for (deal in c("thames", "severn")) {
    pdf <- if (deal == "thames") THAMES else SEVERN
    key <- if (deal == "thames") KEY_T else KEY_S
    both <- extract_deal_terms(pdf, "both", simulated_model_brain(key))
    expect_equal(r_json(extract_deal_terms(pdf)), ref[[deal]]$rules, tolerance = 1e-9)
    expect_equal(r_json(both), ref[[deal]]$both, tolerance = 1e-9)
    expect_equal(r_json(extract_deal_terms(pdf, "model", simulated_model_brain(key, plant = list("classes.B.margin" = 0.018)))),
                 ref[[deal]]$planted, tolerance = 1e-9)
    expect_equal(r_json(analyse_deal_terms(both)), ref[[deal]]$analysis, tolerance = 1e-9)
  }
})

test_that("search over any PDF agrees with Python on Thames (same text) and on Severn pages", {
  r <- search_document(THAMES, "trigger limit per cent", top_k = 2)
  expect_equal(r_json(r), ref$thames$search, tolerance = 1e-9)
  s <- search_document(SEVERN, "trigger limit per cent", top_k = 2)
  # Severn's tables wrap their cells: pdftools and pypdf order those words differently, so chunk texts
  # (and so BM25 scores) can differ on pages 2 to 4. The pages found must still agree.
  expect_equal(vapply(s$results, function(x) x$page, numeric(1)),
               vapply(ref$severn$search$results, function(x) x$page, numeric(1)))
})

test_that("the analyser registry has three tools and returns errors as text", {
  expect_equal(names(ANALYSER_TOOLS), c("extract_deal_terms", "analyse_deal_terms", "search_document"))
  expect_equal(length(TOOLS), 5)
  out <- fromJSON(call_analyser_tool("analyse_deal_terms", list(pdf_path = THAMES)), simplifyVector = FALSE)
  expect_equal(out$checks_passed, 5)
  err <- fromJSON(call_analyser_tool("extract_deal_terms", list(pdf_path = "missing.pdf")))
  expect_match(err$error, "no PDF at")
})

# ------------------------------------------------------------ a reserve counts by what it can pay, not its name
toy_terms <- function(name, can_cover) {
  f <- function(v) list(value = v, page = 1, quote = "", source = "rules", grounded = TRUE)
  cls <- lapply(list(c("A", 90, 0.01), c("B", 10, 0.02)), function(x)
    list(name = f(x[1]), balance = f(as.numeric(x[2])), share = f(NA), margin = f(as.numeric(x[3])), rating = f(NA)))
  list(deal_name = f("Toy"), pool_balance = f(100), classes = cls,
       reserve_funds = list(list(name = f(name), amount = f(2), percent = f(0.02), basis = f(NA),
                                 can_cover_losses = f(can_cover))),
       priority_of_payments = list(combined = list(), revenue = list(), principal = list()),
       triggers = list(), ungrounded = list())
}

test_that("a reserve named liquidity that can cover losses is counted", {
  a <- analyse_deal_terms(toy_terms("Liquidity Reserve Fund", TRUE))
  expect_equal(a$credit_enhancement[[1]]$credit_enhancement, 0.12)
  expect_true(a$reserves[[1]]$counted)
})

test_that("a reserve fund that pays only interest is not counted", {
  a <- analyse_deal_terms(toy_terms("Reserve Fund", FALSE))
  expect_equal(a$credit_enhancement[[1]]$credit_enhancement, 0.1)
  expect_match(a$reserves[[1]]$reason, "^not counted: it pays only fees and interest")
})

test_that("a reserve whose purpose was not found is not counted", {
  a <- analyse_deal_terms(toy_terms("Reserve Fund", NA))
  expect_equal(a$credit_enhancement[[1]]$credit_enhancement, 0.1)
  expect_equal(a$reserves[[1]]$reason, "reserve not counted: what it can pay was not found")
})

test_that("reads_cover gives the same readings as Python", {
  expect_false(reads_cover("The reserve fund is never used to pay principal or deferred consideration."))
  expect_true(reads_cover(paste("The General Reserve Fund covers shortfalls of senior expenses and interest on the",
                                "Class A to D Notes, and debit balances on the Class A to D Principal Deficiency Ledgers;")))
  expect_false(reads_cover("The Liquidity Reserve Fund covers shortfalls of senior expenses and interest on the Class A and B Notes only."))
})
