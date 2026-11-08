# Chapter 17: how cut() places values in bands. Each band includes its upper edge, not its lower edge.
scores <- c(649, 650, 699, 700, 850, NA)
band <- cut(scores, breaks = c(0, 649, 699, 749, 799, 849, 999),
            labels = c("Below 650", "650-699", "700-749", "750-799", "800-849", "850 and above"))
print(data.frame(score = scores, band = as.character(band)))
