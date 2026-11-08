# Tests for the Prospectus Analyser (chapter 26): the logic functions and the Shiny server, no browser.
library(testthat)
library(shiny)
old <- setwd(root)
source(file.path(root, "r", "taragent", "load_analyser.R"))
setwd(old)
source(file.path(root, "r", "vol2", "ch26", "analyser_logic.R"))
source(file.path(root, "r", "vol2", "ch26", "app_server.R"))

key_of <- function(name) jsonlite::fromJSON(sample_path(name, "key"), simplifyVector = FALSE)

test_that("a sample button loads the book's prospectus", {
  testServer(server, {
    session$setInputs(sample_thames = 1)
    expect_equal(doc()$sample, "thames")
    expect_true(file.exists(doc()$path))
    expect_match(output$document, "Thames Auto Receivables")
    session$setInputs(sample_severn = 1)
    expect_equal(doc()$sample, "severn")
  })
})

test_that("rules extraction finds 16 of 16 fields on Thames and 5 of 16 on Severn", {
  testServer(server, {
    session$setInputs(sample_thames = 1, layer = "rules", mode = "simulated", extract = 1)
    expect_equal(terms()$coverage$found, 16)
    expect_match(output$coverage, "^16 of 16 schema fields found\\. Values that failed the page grounding check: 0\\.$")
    session$setInputs(sample_severn = 1, extract = 2)
    expect_equal(terms()$coverage$found, 5)
    expect_match(output$coverage, "^5 of 16 schema fields found \\(missing: ")
  })
})

test_that("both layers with the simulated model complete Severn, and the label says it is simulated", {
  testServer(server, {
    session$setInputs(sample_severn = 1, layer = "both", mode = "simulated", extract = 1)
    expect_equal(terms()$coverage$found, 16)
    expect_match(output$status, "simulated model", fixed = TRUE)
    expect_match(output$status, "not a language model", fixed = TRUE)
    expect_equal(score_against_key(terms(), key_of("severn"))$correct, 76)
  })
})

test_that("a planted wrong value is shown as NOT grounded", {
  brain <- simulated_model_brain(key_of("severn"), plant = list("classes.B.margin" = 0.018))
  terms <- extract_deal_terms(sample_path("severn", "pdf"), "model", brain)
  table <- terms_table(terms)
  expect_equal(table$Grounded[table$Field == "classes[1].margin"], "NOT grounded")
  expect_equal(sum(table$Grounded == "NOT grounded"), 1)
  expect_match(coverage_text(terms), "failed the page grounding check: 1\\.$")
})

test_that("the analysis gives the credit enhancement quoted in the chapter", {
  testServer(server, {
    session$setInputs(sample_thames = 1, layer = "rules", mode = "simulated", extract = 1)
    expect_equal(analysis()$credit_enhancement[[1]]$credit_enhancement, 0.15)
    expect_match(output$ce, "15.000%", fixed = TRUE)
    expect_equal(analysis()$checks_passed, 5)
    session$setInputs(sample_severn = 1, layer = "both", extract = 2)
    expect_equal(analysis()$credit_enhancement[[1]]$credit_enhancement, 0.13955)
    expect_match(output$ce, "13.955%", fixed = TRUE)
    expect_equal(lengths(waterfall_steps(analysis())), c(`Revenue priority of payments` = 17,
                                                         `Principal priority of payments` = 7))
  })
})

test_that("with rules only, Severn's checks are 'not possible', and the reason is shown", {
  terms <- extract_deal_terms(sample_path("severn", "pdf"), "rules")
  checks <- checks_table(analyse_deal_terms(terms))
  expect_true(all(checks$Result == "not possible"))
  expect_true(all(nzchar(checks$Detail)))
})

test_that("replay without a recording shows the pending line instead of failing", {
  testServer(server, {
    session$setInputs(sample_severn = 1, layer = "model", mode = "replay", extract = 1)
    if (!file.exists(file.path(root, "r", "recordings", "vol2-partE-extract-severn.jsonl"))) {
      expect_equal(output$status, PENDING)
      expect_null(terms())
    }
  })
})

test_that("the simulated model refuses an uploaded document that has no answer key", {
  run <- run_extraction(sample_path("severn", "pdf"), "model", "simulated", sample = NULL)
  expect_null(run$terms)
  expect_match(run$message, "only works on the book's two sample prospectuses")
})

test_that("a live brain without Ollama gives a message, not a crash", {
  old_host <- Sys.getenv("OLLAMA_HOST")
  Sys.setenv(OLLAMA_HOST = "http://127.0.0.1:9")          # port 9: nothing listens there
  on.exit(Sys.setenv(OLLAMA_HOST = old_host))
  run <- run_extraction(sample_path("severn", "pdf"), "model", "live", sample = "severn")
  expect_null(run$terms)
  expect_match(run$message, "^Extraction failed:")
  ans <- ask_document(sample_path("severn", "pdf"), "What is the arrears trigger?", "live",
                      recording = tempfile(fileext = ".jsonl"))
  expect_match(ans$answer, "^The model could not run:")
})

test_that("questions are answered from the uploaded document with page citations", {
  testServer(server, {
    session$setInputs(sample_severn = 1, question = "What is the limit of the arrears trigger?", ask_mode = "rules", ask = 1)
    expect_match(answer()$answer, "^Best passage \\(page [0-9]+, no model used\\)")
    expect_true(length(answer()$passages) >= 1)
  })
})

test_that("surveillance with the extracted limits agrees with the agent in all 12 periods", {
  terms <- extract_deal_terms(sample_path("thames", "pdf"), "rules")
  s <- surveillance_table(terms)
  expect_equal(nrow(s), 12)
  expect_true(all(s$`Agent agrees` == "yes"))
  expect_equal(which(s$Result == "BREACHED")[1], 10)
  r <- report_against_limits(file.path(root, "data", "investor_reports", "investor_report_2026_10.json"), terms)
  expect_equal(r$Result, c("pass", "BREACHED"))
})

test_that("an upload that is not a PDF is refused", {
  f <- tempfile(fileext = ".pdf"); writeLines("hello", f)
  expect_equal(check_pdf(f), "This file is not a PDF.")
  expect_null(check_pdf(sample_path("thames", "pdf")))
})

test_that("the exports contain the terms and the analysis", {
  terms <- extract_deal_terms(sample_path("thames", "pdf"), "rules")
  analysis <- analyse_deal_terms(terms)
  j <- tempfile(fileext = ".json"); export_json(terms, analysis, j)
  back <- jsonlite::fromJSON(j, simplifyVector = FALSE)
  expect_equal(back$terms$classes[[1]]$balance$value, 62964482.91)
  expect_equal(back$analysis$checks_passed, 5)
  x <- tempfile(fileext = ".xlsx"); export_excel(terms, analysis, x)
  expect_equal(openxlsx::getSheetNames(x), c("Deal terms", "Credit enhancement", "Checks", "Triggers"))
  ce <- openxlsx::read.xlsx(x, "Credit enhancement")
  expect_equal(ce$Credit.enhancement[1], "15.000%")
})

test_that("a scanned PDF (no text layer) gets a clear message instead of an empty table", {
  img <- pdftools::pdf_render_page(sample_path("thames", "pdf"), page = 1, dpi = 40)
  scanned <- tempfile(fileext = ".pdf")
  grDevices::pdf(scanned); graphics::par(mar = c(0, 0, 0, 0)); graphics::plot.new()
  graphics::rasterImage(grDevices::as.raster(aperm(array(as.integer(img), dim(img)), c(3, 2, 1)) / 255), 0, 0, 1, 1)
  invisible(grDevices::dev.off())
  run <- run_extraction(scanned, "rules")
  expect_null(run$terms)
  expect_match(run$message, "needs OCR")
})

test_that("the reference answer to the practical task gets full marks, and the solutions run", {
  old <- setwd(root); on.exit(setwd(old))
  out <- system2("Rscript", c("r/vol2/ch26/check_ch26.R", "--solution"), stdout = TRUE)
  expect_equal(tail(out, 1), "6 of 6 checks passed: full mark.")
  s4 <- system2("Rscript", "r/vol2/ch26/solutions/ex_26_4_servicer_rule.R", stdout = TRUE)
  expect_equal(s4[1], "Rule found: Marlowe Building Society on page 2 ")
  expect_equal(s4[3], "Fields found: 6 of 16 (was 5)")
  s5 <- system2("Rscript", "r/vol2/ch26/solutions/ex_26_5_wrong_pool.R", stdout = TRUE)
  expect_equal(s5[3], "Paths that failed: pool_balance ")
})

test_that("bad uploads give a plain sentence, never R's error", {
  nul <- tempfile(fileext = ".pdf"); writeBin(as.raw(c(0xff, 0xfe, 0x00, 0x41)), nul)
  expect_equal(check_pdf(nul), "This file is not a PDF.")
  tape <- tempfile(fileext = ".csv"); writeLines(c("a,b", "1,2"), tape)
  report <- tempfile(fileext = ".json"); writeLines("[1, 2]", report)
  testServer(server, {
    session$setInputs(sample_thames = 1, layer = "rules", mode = "simulated", extract = 1)
    session$setInputs(tape = list(datapath = tape, name = "other.csv"))
    expect_error(output$tape_check, "The loan tape \\(CSV in the book's format\\) could not be read")
    session$setInputs(report = list(datapath = report, name = "report.json"))
    expect_error(output$report_check, "The investor report \\(JSON in the book's format\\) could not be read")
  })
})
