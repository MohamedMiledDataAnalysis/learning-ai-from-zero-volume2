# The page: a sidebar to choose the document and the extraction, and five tabs for the results.
library(shiny)
library(bslib)

ui <- page_sidebar(
  title = "Prospectus Analyser",
  fillable = FALSE,                          # let long tables flow down the page instead of squeezing them
  theme = bs_theme(primary = "#1F2F54", secondary = "#B8892B"),
  tags$style(".ungrounded { color: #9B2D20; font-weight: bold; } #answer { white-space: pre-wrap; }"),
  sidebar = sidebar(
    width = 330,
    h6("1. The prospectus"),
    fileInput("pdf", NULL, accept = ".pdf", buttonLabel = "Upload PDF"),
    actionButton("sample_thames", "Sample: Thames (auto loans)", class = "btn-sm"),
    actionButton("sample_severn", "Sample: Severn (mortgages)", class = "btn-sm"),
    textOutput("document"),
    h6("2. Extraction"),
    radioButtons("layer", "Layer", c("rules", "model", "both"), selected = "rules", inline = TRUE),
    radioButtons("mode", "Model brain", c("simulated", "replay", "live", "record"), selected = "simulated", inline = TRUE),
    actionButton("extract", "Extract the deal terms", class = "btn-primary"),
    h6("3. Optional data"),
    fileInput("tape", "Loan tape (CSV)", accept = ".csv"),
    fileInput("report", "Investor report (JSON)", accept = ".json"),
    checkboxInput("thames_data", "Use the Thames sample data", value = FALSE)
  ),
  navset_card_tab(
    id = "tabs", height = "auto",
    nav_panel("Deal terms",
              textOutput("status"), textOutput("coverage"),
              DT::DTOutput("terms", height = "auto", fill = FALSE)),   # the table grows with its rows
    nav_panel("Analysis",
              fluidRow(column(4, plotOutput("capital", height = "420px")),
                       column(8, h6("Credit enhancement"), tableOutput("ce"))),
              h6("Consistency checks"), tableOutput("checks"),
              h6("Triggers"), tableOutput("triggers"),
              h6("Waterfall"), uiOutput("waterfall")),
    nav_panel("Ask",
              textInput("question", "Question about the prospectus", value = "What is the limit of the arrears trigger?",
                        width = "100%"),
              radioButtons("ask_mode", "Brain", c("rules", "replay", "live"), selected = "rules", inline = TRUE),
              actionButton("ask", "Ask"),
              h6("Answer"), verbatimTextOutput("answer"),
              h6("Passages used"), tableOutput("passages")),
    nav_panel("Surveillance",
              p("The trigger tests rerun with the limits read from the prospectus, compared with the agent's own tool."),
              tableOutput("surveillance"),
              h6("Uploaded investor report against the prospectus limits"), tableOutput("report_check"),
              h6("Uploaded loan tape"), verbatimTextOutput("tape_check")),
    nav_panel("Export",
              p("Download the extracted terms and the analysis."),
              downloadButton("download_json", "JSON"), downloadButton("download_excel", "Excel"))
  )
)
