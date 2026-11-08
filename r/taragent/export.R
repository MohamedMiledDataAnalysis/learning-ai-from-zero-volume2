# Export the monthly surveillance pack to Excel (R version of tar_agent/export.py).
#
# One workbook per period, four sheets: Summary, Triggers, Arrears by region, Note.
# The openxlsx package writes .xlsx files without Excel installed.

suppressPackageStartupMessages(library(openxlsx))

HEADER_STYLE <- createStyle(fontColour = "#FFFFFF", fgFill = "#1F2F54", textDecoration = "bold")

add_sheet <- function(wb, title, table, widths) {
  addWorksheet(wb, title)
  writeData(wb, title, table, headerStyle = HEADER_STYLE)
  setColWidths(wb, title, cols = seq_along(widths), widths = widths)
}

# Write out_dir/surveillance_pack_2026_MM.xlsx and return its path.
export_monthly_pack <- function(period, out_dir) {
  rep <- investor_report(period)
  trig <- run_trigger_tests(period)
  regions <- stratify_pool("region", period, "balance_90plus")$rows
  note <- draft_surveillance_note(period)$note_markdown
  pool <- rep$pool

  wb <- createWorkbook(creator = "taragent")
  # Summary: a column of labels and a column of values. Text and numbers share the column,
  # so the values are written one cell at a time, each with its own type.
  addWorksheet(wb, "Summary")
  writeData(wb, "Summary", data.frame(Item = "Item", Value = "Value"), colNames = FALSE)
  addStyle(wb, "Summary", HEADER_STYLE, rows = 1, cols = 1:2)
  items <- list(Deal = rep$deal, `Collection period` = period, `Payment date` = rep$payment_date,
                `Opening pool balance` = pool$opening_balance, `Closing pool balance` = pool$closing_balance,
                Prepayments = pool$prepayments, Defaults = pool$defaults, Recoveries = pool$recoveries,
                `Loans outstanding` = pool$loans_outstanding,
                `Principal payment mode` = trig$principal_payment_mode)
  for (i in seq_along(items)) {
    writeData(wb, "Summary", names(items)[i], startRow = i + 1, startCol = 1)
    writeData(wb, "Summary", items[[i]], startRow = i + 1, startCol = 2)
  }
  addStyle(wb, "Summary", createStyle(numFmt = "#,##0.00"), rows = 5:9, cols = 2)   # amounts in pounds
  addStyle(wb, "Summary", createStyle(numFmt = "#,##0"), rows = 10, cols = 2)       # number of loans
  setColWidths(wb, "Summary", cols = 1:2, widths = c(28, 40))

  tests <- do.call(rbind, lapply(trig$tests, function(t) data.frame(
    Test = t$test, Value = t$value, Limit = t$limit, Headroom = t$headroom,
    Breached = if (t$breached) "YES" else "no", `Agrees with report` = if (t$agrees_with_report) "yes" else "NO",
    check.names = FALSE)))
  add_sheet(wb, "Triggers", tests, c(28, 12, 10, 12, 10, 18))
  addStyle(wb, "Triggers", createStyle(numFmt = "0.00%"), rows = 2:(nrow(tests) + 1), cols = 2:4, gridExpand = TRUE)

  arrears <- do.call(rbind, lapply(regions, function(r) data.frame(
    Region = r$group, `90+ balance` = r$balance_90plus, `Share of 90+` = r$share_of_total,
    `90+ within region` = r$ratio_within_group, check.names = FALSE)))
  add_sheet(wb, "Arrears by region", arrears, c(26, 16, 14, 18))
  addStyle(wb, "Arrears by region", createStyle(numFmt = "#,##0.00"), rows = 2:(nrow(arrears) + 1), cols = 2)
  addStyle(wb, "Arrears by region", createStyle(numFmt = "0.0%"), rows = 2:(nrow(arrears) + 1), cols = 3:4,
           gridExpand = TRUE)

  # Blank lines of the note are left as empty cells (NA), not as cells holding empty text, as in Python.
  note_lines <- strsplit(note, "\n", fixed = TRUE)[[1]]
  note_lines[note_lines == ""] <- NA
  add_sheet(wb, "Note", data.frame(`Surveillance note` = note_lines, check.names = FALSE), 110)

  dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
  path <- file.path(out_dir, sprintf("surveillance_pack_2026_%02d.xlsx", as.integer(period)))
  saveWorkbook(wb, path, overwrite = TRUE)
  path
}
