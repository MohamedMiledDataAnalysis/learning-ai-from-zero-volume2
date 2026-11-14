# The server: what happens when the analyst loads a document, extracts, asks or exports.
# Every figure comes from the shared tools (r/taragent) through analyser_logic.R.

# Run a step on an uploaded file; an R error becomes a plain sentence on the page.
plainly <- function(expr, what) {
  tryCatch(expr, error = function(e) {
    if (inherits(e, "shiny.silent.error")) stop(e)        # req() and validate() keep their meaning
    shiny::validate(shiny::need(FALSE, sprintf("%s could not be read: %s", what, conditionMessage(e))))
  })
}

server <- function(input, output, session) {
  doc <- reactiveVal(NULL)      # list(path, name, sample): the document being analysed

  observeEvent(input$pdf, {
    problem <- check_pdf(input$pdf$datapath)
    if (!is.null(problem)) return(showNotification(problem, type = "error"))
    doc(list(path = input$pdf$datapath, name = input$pdf$name, sample = NULL))
  })
  observeEvent(input$sample_thames, doc(list(path = sample_path("thames", "pdf"), name = SAMPLES$thames$label, sample = "thames")))
  observeEvent(input$sample_severn, doc(list(path = sample_path("severn", "pdf"), name = SAMPLES$severn$label, sample = "severn")))
  output$document <- renderText(if (is.null(doc())) "No document yet." else paste("Document:", doc()$name))

  # Extraction runs only when the button is pressed.
  result <- eventReactive(input$extract, {
    req(doc())
    tryCatch(run_extraction(doc()$path, input$layer, input$mode, doc()$sample),
             error = function(e) list(terms = NULL, message = paste("The PDF could not be read:", conditionMessage(e))))
  })
  terms <- reactive(result()$terms)
  analysis <- reactive({ req(terms()); analyse_deal_terms(terms()) })

  output$status <- renderText(result()$message)
  output$coverage <- renderText({ req(terms()); coverage_text(terms()) })
  output$terms <- DT::renderDT({
    req(terms())
    tt <- terms_table(terms())
    shiny::validate(shiny::need(!is.null(tt), "No value was extracted from this document."))
    DT::datatable(tt, rownames = FALSE, options = list(pageLength = 15, scrollX = TRUE)) |>
      DT::formatStyle("Grounded", color = DT::styleEqual("NOT grounded", "#9B2D20"),
                      fontWeight = DT::styleEqual("NOT grounded", "bold"))
  })

  output$capital <- renderPlot({ p <- capital_structure_plot(analysis()); shiny::validate(shiny::need(p, "No classes extracted.")); p },
                               width = 460, height = 420)     # a fixed size: the card layout can report a zero width
  output$ce <- renderTable(ce_table(analysis()))
  output$checks <- renderTable(checks_table(analysis()))
  output$triggers <- renderTable({ req(terms()); trigger_table(terms()) })
  output$waterfall <- renderUI({
    steps <- waterfall_steps(analysis())
    columns <- lapply(names(steps), function(title) {
      items <- steps[[title]]
      if (!length(items)) return(div(strong(title), p("Not extracted.")))
      div(strong(title), tags$ol(lapply(items, tags$li)))
    })
    do.call(fluidRow, lapply(columns, function(x) column(12 / length(columns), x)))
  })

  # Questions are answered only when the button is pressed.
  answer <- eventReactive(input$ask, {
    req(doc())
    ask_document(doc()$path, input$question, input$ask_mode, sample = doc()$sample)
  })
  output$answer <- renderText(answer()$answer)
  output$passages <- renderTable({
    hits <- answer()$passages
    if (!length(hits)) return(NULL)
    data.frame(Page = vapply(hits, function(h) as.integer(h$page), 1L),
               Score = vapply(hits, function(h) h$score, 0), Passage = vapply(hits, function(h) h$text, ""))
  })

  output$surveillance <- renderTable({
    req(terms())
    shiny::validate(shiny::need(input$thames_data, "Tick 'Use the Thames sample data' to run the trigger tests on the Thames loans."),
             shiny::need(identical(doc()$sample, "thames"), "The Thames data only matches the Thames prospectus."))
    surveillance_table(terms())
  })
  output$report_check <- renderTable({
    req(terms(), input$report)
    plainly(report_against_limits(input$report$datapath, terms()), "The investor report (PDF or Excel)")
  })
  output$tape_check <- renderText({
    req(input$tape)
    files <- tape_files(input$tape$datapath)
    v <- plainly({
      if (is.null(files$template)) stop("no file starts with the field AUTL1 of the FCA template", call. = FALSE)
      validate_loan_tape(files$template, files$supplementary)
    }, "The loan tape (FCA template and supplementary file)")
    sprintf("%d rows received, %d issues found, cleaned balance %s.", v$rows_received, v$issues_found,
            formatC(v$balance_after_cleaning, format = "f", digits = 2, big.mark = ","))
  })

  # The three files together. With the sample box ticked, the Thames files fill in what was not uploaded.
  checks <- reactive({
    req(terms())
    files <- if (!is.null(input$tape)) tape_files(input$tape$datapath) else
      if (isTRUE(input$thames_data)) list(template = POOL_CUT, supplementary = SUPPLEMENTARY) else list()
    report <- if (!is.null(input$report)) input$report$datapath else
      if (isTRUE(input$thames_data)) investor_report_path(12) else NULL
    plainly(deal_check(terms(), files$template, report, files$supplementary), "A file")
  })
  output$deal_check_status <- renderText({
    counts <- table(factor(checks()$Result, levels = c("pass", "FAIL", "BREACHED", "file not loaded")))
    paste0(paste(counts[counts > 0], names(counts)[counts > 0], collapse = ", "), ".")
  })
  output$deal_check <- renderTable(checks())

  output$download_json <- downloadHandler(
    filename = function() "deal_terms.json",
    content = function(file) export_json(terms(), analysis(), file))
  output$download_excel <- downloadHandler(
    filename = function() "deal_terms.xlsx",
    content = function(file) export_excel(terms(), analysis(), file))
}
