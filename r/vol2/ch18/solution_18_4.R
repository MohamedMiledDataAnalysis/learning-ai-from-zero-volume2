# Solution 18.4: how principal was shared between the classes before and after the breach.
source("r/taragent/load.R")

for (period in c(9, 10)) {
  rep <- investor_report(period)
  mode <- if (isTRUE(rep$triggers$sequential_payment)) "sequential" else "pro rata"
  cat(sprintf("Period %d (%s): payment date %s\n", period, mode, rep$payment_date))
  total <- sum(vapply(rep$notes, function(n) n$principal_paid, 0))
  for (n in rep$notes) {
    cat(sprintf("  Class %s: opening %15s  principal %13s  (%6.2f%%)\n", n$class, money(n$opening_balance),
                money(n$principal_paid), 100 * n$principal_paid / total))
  }
  cat("\n")
}
