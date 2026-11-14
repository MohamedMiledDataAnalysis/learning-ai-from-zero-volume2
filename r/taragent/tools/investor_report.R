# Read the cash manager's monthly investor report (PDF or Excel) into the figures the tools use
# (R version of tar_agent/tools/investor_report.py).
#
# Larkmead Bank plc publishes each report twice: a PDF for reading and an Excel workbook with
# the same figures. From the PDF, the text of each page is taken in layout mode (one table row
# per line, as pdftools gives it); from the workbook, each row of each sheet is written as one
# line in the same form. Each figure is then found by its row label, and the result is the same
# list, with the same names in the same order, as the Python reader returns.

IR_NUMBER <- "-?[0-9,]+(?:\\.[0-9]+)?%?"

report_lines <- function(pdf_path) {
  lines <- unlist(strsplit(pdftools::pdf_text(pdf_path), "\n", fixed = TRUE))
  lines <- gsub("—", "-", lines, fixed = TRUE)
  lines <- trimws(gsub("\\s+", " ", lines))
  lines[nzchar(lines)]
}

# "1,234.56" -> 1234.56; "4.4000%" -> 0.044 (per cent turned into a fraction).
ir_number <- function(text) {
  if (endsWith(text, "%")) return(round(as.numeric(gsub(",", "", sub("%$", "", text))) / 100, 6))
  as.numeric(gsub(",", "", text))
}

ir_regex_escape <- function(s) gsub("([][{}()+*^$|\\\\?.])", "\\\\\\1", s)

# The `count` values that follow `label` on its line. The label starts the line, or follows a value of
# the table printed to its left.
ir_after <- function(lines, label, count = 1) {
  values <- paste(rep(paste0("(", IR_NUMBER, ")"), count), collapse = " ")
  pattern <- paste0("(?:^|[0-9] |% )", ir_regex_escape(label), " ", values)
  for (line in lines) {
    m <- regmatches(line, regexec(pattern, line, perl = TRUE))[[1]]
    if (length(m)) return(vapply(m[-1], ir_number, numeric(1), USE.NAMES = FALSE))
  }
  stop(sprintf("investor report: no line with '%s' followed by %d value(s)", label, count), call. = FALSE)
}

ir_word_after <- function(lines, label) {
  hit <- lines[startsWith(lines, paste0(label, " "))]
  if (!length(hit)) stop(sprintf("investor report: no line starting with '%s'", label), call. = FALSE)
  strsplit(substring(hit[1], nchar(label) + 2), " ", fixed = TRUE)[[1]][1]
}

ir_last_word <- function(lines, label) {
  hit <- lines[startsWith(lines, paste0(label, " "))][1]
  tail(strsplit(hit, " ", fixed = TRUE)[[1]], 1)
}

ir_iso <- function(dmy) format(as.Date(dmy, format = "%d/%m/%Y"), "%Y-%m-%d")

ir_money <- function(x) round(as.numeric(x), 2)

# Every row of every sheet as one line of text, written the way the PDF shows it.
IR_PERCENT_LABELS <- c("Compounded Daily SONIA", "CPR", "Cumulative Default Ratio", "90+ Day Arrears Ratio")

ir_cell_text <- function(label, column, value) {
  if (is.character(value)) {
    if (grepl("^[0-9]{4}-[0-9]{2}-[0-9]{2}$", value)) return(format(as.Date(value), "%d/%m/%Y"))
    return(value)
  }
  if (identical(column, "Margin")) return(sprintf("%.2f%%", value * 100))
  if (identical(column, "Coupon")) return(sprintf("%.4f%%", value * 100))
  if (any(startsWith(label, IR_PERCENT_LABELS))) return(sprintf("%.4f%%", value * 100))
  if (label == "Pool Factor" || identical(column, "Note Factor")) return(sprintf("%.6f", value))
  if ((value == round(value) && label %in% c("Collection Period Number", "Days in Interest Period",
                                              "Number of Loans Outstanding")) || identical(column, "Number of Loans"))
    return(formatC(value, format = "d", big.mark = ","))
  formatC(value, format = "f", digits = 2, big.mark = ",")
}

workbook_lines <- function(xlsx_path) {
  lines <- character(0)
  for (sheet in readxl::excel_sheets(xlsx_path)) {
    cells <- readxl::read_excel(xlsx_path, sheet = sheet, col_names = FALSE, col_types = "list",
                                .name_repair = "minimal")
    header <- NULL
    for (i in seq_len(nrow(cells))) {
      row <- Filter(function(c) !is.null(c) && !(length(c) == 1 && is.na(c)), lapply(cells[i, ], `[[`, 1))
      if (!length(row)) next
      if (all(vapply(row, is.character, logical(1))) && length(row) > 2) { header <- unname(unlist(row)); next }
      label <- as.character(row[[1]])
      out <- label
      for (k in seq_along(row)[-1]) {
        column <- if (!is.null(header) && k <= length(header)) header[k] else ""
        out <- c(out, ir_cell_text(label, column, row[[k]]))
      }
      lines <- c(lines, paste(out, collapse = " "))
    }
  }
  lines
}

# The format is recognised from the file itself: an Excel workbook starts with PK, a PDF with %PDF.
read_investor_report <- function(path) {
  start <- readBin(path, "raw", 4)
  kind <- if (identical(start[1:2], charToRaw("PK"))) "xlsx" else if (identical(start, charToRaw("%PDF"))) "pdf" else
    stop(sprintf("%s is neither a PDF nor an Excel workbook", path), call. = FALSE)
  cached(paste0("investor_report:", kind, ":", normalizePath(path)), function() {
    lines <- if (kind == "pdf") report_lines(path) else workbook_lines(path)
    pool <- list(loans_outstanding = as.integer(ir_after(lines, "Number of Loans Outstanding")))
    labels <- c(opening_balance = "Opening Pool Balance", principal_received = "Scheduled Principal Received",
                prepayments = "Prepayments", defaults = "Defaults", closing_balance = "Closing Pool Balance",
                interest_collections = "Interest Collections", recoveries = "Recoveries",
                cumulative_defaults = "Cumulative Defaults", cumulative_recoveries = "Cumulative Recoveries")
    for (key in names(labels)) pool[[key]] <- ir_money(ir_after(lines, labels[[key]]))
    pool$pool_factor <- ir_after(lines, "Pool Factor")
    pool$cpr <- ir_after(lines, "CPR (annualised, this period)")

    arrears <- list()
    buckets <- c("Current (0 instalments)", "1 instalment (30-59 days)", "2 instalments (60-89 days)",
                 "3 instalments (90+ days)")
    for (k in 0:3) {
      v <- ir_after(lines, paste("Arrears", buckets[k + 1]), 2)
      arrears[[paste0(k, "_instalments")]] <- list(count = as.integer(v[1]), balance = ir_money(v[2]))
    }

    waterfall <- list()
    wf <- paste0("^([0-9]+\\. .+?) (", IR_NUMBER, ") (", IR_NUMBER, ")$")
    for (line in lines) {
      m <- regmatches(line, regexec(wf, line, perl = TRUE))[[1]]
      if (length(m)) waterfall[[length(waterfall) + 1]] <-
          list(item = m[2], due = ir_money(ir_number(m[3])), paid = ir_money(ir_number(m[4])))
    }

    notes <- list()
    nt <- paste0("^Class ([A-Z]) (\\S+) (\\S+) ", paste(rep(paste0("(", IR_NUMBER, ")"), 8), collapse = " "), "$")
    for (line in lines) {
      m <- regmatches(line, regexec(nt, line, perl = TRUE))[[1]]
      if (length(m)) {
        v <- vapply(m[5:12], ir_number, numeric(1), USE.NAMES = FALSE)
        notes[[length(notes) + 1]] <- list(
          class = m[2], rating = m[4], margin = round(v[1], 4), coupon = v[2], opening_balance = ir_money(v[4]),
          interest_paid = ir_money(v[5]), principal_paid = ir_money(v[6]), closing_balance = ir_money(v[7]),
          initial_balance = ir_money(v[3]), factor = v[8])
      }
    }

    test <- function(label) {
      v <- ir_after(lines, label, 2)
      list(value = v[1], limit = v[2], breached = ir_last_word(lines, label) == "Breached")
    }
    list(
      deal = lines[grepl(" (plc|PLC)$", lines)][1],
      period = as.integer(ir_after(lines, "Collection Period Number")),
      collection_period_end = ir_iso(ir_word_after(lines, "Collection Period End Date")),
      payment_date = ir_iso(ir_word_after(lines, "Payment Date")),
      sonia = ir_after(lines, "Compounded Daily SONIA for the Interest Period"),
      pool = pool,
      arrears = arrears,
      available_funds = ir_money(ir_after(lines, "Total Available Funds")),
      waterfall = waterfall,
      reserve_fund = list(required = ir_money(ir_after(lines, "Reserve Fund Required Amount")),
                          drawn = ir_money(ir_after(lines, "Reserve Fund Drawn in the Period")),
                          balance = ir_money(ir_after(lines, "Reserve Fund Balance after the Payment Date"))),
      notes = notes,
      principal_deficiency = ir_money(ir_after(lines, "Principal Deficiency after the Payment Date")),
      triggers = list(
        cumulative_default_ratio = test("Cumulative Default Ratio"),
        arrears_90_ratio = test("90+ Day Arrears Ratio"),
        reserve_fund_shortfall = list(breached = ir_last_word(lines, "Reserve Fund at the Required Amount") == "Breached"),
        sequential_payment = ir_word_after(lines, "Principal Payment Basis on this Payment Date") == "Sequential",
        newly_breached_this_period = ir_word_after(lines, "Trigger Event Occurred in this Collection Period") == "Yes"),
      residual_to_originator = ir_money(ir_after(lines, "Residual Amount to the Originator"))
    )
  })
}
