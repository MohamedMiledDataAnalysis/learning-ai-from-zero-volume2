# Tests for the Shiny app's server logic (chapter 25), without opening a browser.
library(testthat)
library(shiny)
old <- setwd(root)
source(file.path(root, "r", "taragent", "load.R"))
setwd(old)
source(file.path(root, "r", "vol2", "ch25", "app_server.R"))

test_that("the trigger table and the payment mode follow the chosen period", {
  testServer(server, {
    session$setInputs(period = "10")
    expect_equal(trig()$principal_payment_mode, "sequential")
    expect_match(output$triggers, "BREACHED")
    expect_equal(output$payment_mode, "Principal is paid sequentially (Class A first).")
    session$setInputs(period = "9")
    expect_equal(output$payment_mode, "Principal is paid pro rata.")
  })
})

test_that("the regional table starts with the North West in October", {
  testServer(server, {
    session$setInputs(period = "10")
    expect_equal(regions()$rows[[1]]$group, "North West")
    expect_match(output$regions, "North West")
  })
})

test_that("the agent answers only when the button is pressed", {
  testServer(server, {
    session$setInputs(period = "10", question = "What is the 90+ day arrears ratio in period 10?", mode = "rules")
    expect_error(answer())                       # no click yet: nothing to show
    session$setInputs(ask = 1)
    expect_match(answer(), "1.32%", fixed = TRUE)
    session$setInputs(mode = "replay", ask = 2)
    if (file.exists(file.path(RECORDINGS, "shiny_question.jsonl"))) {
      expect_match(answer(), "1.32%", fixed = TRUE)   # the recorded reply of qwen2.5:7b
    } else {
      expect_equal(answer(), PENDING)            # no recording yet in the repository
    }
  })
})

test_that("January shows no 90+ arrears and pro rata payment", {
  testServer(server, {
    session$setInputs(period = "1")
    expect_true(all(vapply(regions()$rows, function(r) r$balance_90plus == 0, TRUE)))
    expect_equal(output$payment_mode, "Principal is paid pro rata.")
  })
})

test_that("a live brain without Ollama gives a sentence, not a crash", {
  withr::local_envvar(OLLAMA_HOST = "http://127.0.0.1:9")   # port 9: nothing listens, whether or not Ollama runs
  testServer(server, {
    session$setInputs(period = "10", question = "Run the trigger tests for period 10.", mode = "live", ask = 1)
    expect_match(answer(), "^The agent could not run:")
  })
})
