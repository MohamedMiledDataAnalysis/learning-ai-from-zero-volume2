# The server: what happens when the analyst changes the period or asks a question.
# Every figure comes from the agent's tools (r/taragent); nothing is computed here.

PENDING <- "[Recording pending: run python record_all.py with Ollama installed, then rebuild]"

server <- function(input, output, session) {
  period <- reactive(as.integer(input$period))

  # Run each tool once per period; the outputs below reuse the result.
  trig <- reactive(run_trigger_tests(period()))
  regions <- reactive(stratify_pool("region", period(), "balance_90plus"))

  output$triggers <- renderTable({
    do.call(rbind, lapply(trig()$tests, function(t) data.frame(
      Test = t$test, Value = pct(t$value), Limit = pct(t$limit),
      Result = if (t$breached) "BREACHED" else "pass")))
  })

  output$payment_mode <- renderText(sprintf("Principal is paid %s.",
    if (trig()$principal_payment_mode == "sequential") "sequentially (Class A first)" else "pro rata"))

  output$regions <- renderTable({
    rows <- head(regions()$rows, 5)
    data.frame(Region = vapply(rows, function(r) r$group, ""),
               `90+ balance` = vapply(rows, function(r) money(r$balance_90plus), ""),
               `Share of 90+` = vapply(rows, function(r) pct(r$share_of_total, 1), ""),
               check.names = FALSE)
  })

  output$note <- renderUI({
    HTML(commonmark::markdown_html(draft_surveillance_note(period())$note_markdown))
  })

  # The agent runs only when the button is pressed, not on every keystroke.
  answer <- eventReactive(input$ask, {
    recording <- file.path(RECORDINGS, "shiny_question.jsonl")     # recorded for the default question only
    recorded <- "What is the 90+ day arrears ratio in period 10?"
    if (input$mode == "replay" && input$question != recorded)
      return(paste0("Replay holds one recorded answer, to the question \"", recorded, "\". Choose rules, or live with Ollama."))
    if (input$mode == "replay" && !(file.exists(recording) && file.size(recording) > 0)) return(PENDING)
    run <- tryCatch(ask(input$question, input$mode, recording, log = function(m) invisible(NULL)),
                    error = function(e) list(answer = paste("The agent could not run:", conditionMessage(e))))
    run$answer
  })
  output$answer <- renderText(answer())
}
