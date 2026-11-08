# The page the analyst sees: a sidebar to choose the period and ask a question,
# and four panels for the results.
library(shiny)

ui <- fluidPage(
  # Smaller headings inside the note, and an answer box that wraps long lines.
  tags$style("#note h1 { font-size: 20px; } #note h2 { font-size: 16px; } #answer { white-space: pre-wrap; }"),
  titlePanel("Thames Auto Receivables 2026-1 — surveillance"),
  sidebarLayout(
    sidebarPanel(
      selectInput("period", "Collection period", choices = setNames(1:12, month.name), selected = 10),
      hr(),
      textInput("question", "Ask the agent", value = "What is the 90+ day arrears ratio in period 10?"),
      radioButtons("mode", "Brain", choices = c("rules", "replay", "live"), selected = "rules", inline = TRUE),
      actionButton("ask", "Ask"),
      width = 3
    ),
    mainPanel(
      h4("Trigger tests"),
      tableOutput("triggers"),
      textOutput("payment_mode"),
      h4("90+ day arrears by region"),
      tableOutput("regions"),
      h4("Draft surveillance note"),
      uiOutput("note"),
      h4("Agent"),
      verbatimTextOutput("answer"),
      width = 9
    )
  )
)
