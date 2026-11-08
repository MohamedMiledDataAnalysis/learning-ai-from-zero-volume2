# Solution 23.6: add a fifth sheet, the pool by product, to the pack of period 10.
source("r/taragent/load.R")

folder <- tempfile()
path <- export_monthly_pack(10, folder)
wb <- loadWorkbook(path)                                   # open the pack written by the tool
rows <- stratify_pool("product", 10)$rows
table <- data.frame(Product = vapply(rows, function(r) r$group, ""),
                    Balance = vapply(rows, function(r) r$balance, 0),
                    Share = vapply(rows, function(r) r$share_of_total, 0))
addWorksheet(wb, "Pool by product")
writeData(wb, "Pool by product", table, headerStyle = HEADER_STYLE)
addStyle(wb, "Pool by product", createStyle(numFmt = "#,##0.00"), rows = 2:3, cols = 2)
addStyle(wb, "Pool by product", createStyle(numFmt = "0.00%"), rows = 2:3, cols = 3)
saveWorkbook(wb, path, overwrite = TRUE)
cat("Sheets:", paste(getSheetNames(path), collapse = ", "), "\n")
print(read.xlsx(path, "Pool by product"), row.names = FALSE)
unlink(folder, recursive = TRUE)
