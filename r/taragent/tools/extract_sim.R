# A stand-in for a model, for the tests and the book's reproducible runs of the model layer
# (R version of tar_agent/tools/extract_sim.py). It is a rule brain, NOT a language model:
# it reads which section the prompt asks for and replies with the JSON a perfect model would
# write, taken from the answer key. plant = list("classes.B.margin" = 0.018) writes one wrong value.

plain_field <- function(f) list(value = f$value, page = f$page, quote = f$quote)

section_reply <- function(key, name, plant = list()) {
  data <- switch(name,
    overview = list(deal_name = plain_field(key$deal_name), currency = plain_field(key$currency),
                    pool_balance = plain_field(key$pool_balance),
                    parties = lapply(key$parties, plain_field), dates = lapply(key$dates, plain_field)),
    classes = list(classes = lapply(key$classes, function(c) {
      row <- lapply(c, plain_field)
      for (k in names(row)) {
        path <- sprintf("classes.%s.%s", c$name$value, k)
        if (!is.null(plant[[path]])) row[[k]]$value <- plant[[path]]
      }
      row
    })),
    reserve_funds = list(reserve_funds = lapply(key$reserve_funds, function(r) lapply(r, plain_field))),
    priority_of_payments = list(priority_of_payments = lapply(key$priority_of_payments,
                                                              function(v) lapply(v, plain_field))),
    triggers = list(triggers = lapply(key$triggers, function(t) lapply(t, plain_field))),
    eligibility = list(eligibility_criteria = lapply(key$eligibility_criteria, plain_field)),
    list(risk_retention = plain_field(key$risk_retention)))
  to_json(data)
}

simulated_model_brain <- function(answer_key, plant = list()) {
  rule_brain(function(memory) {
    users <- Filter(function(m) m$role == "user" && grepl("SECTION:", m$content, fixed = TRUE), memory)
    prompt <- users[[length(users)]]$content
    name <- trimws(strsplit(strsplit(prompt, "SECTION:", fixed = TRUE)[[1]][2], "\n", fixed = TRUE)[[1]][1])
    list(content = section_reply(answer_key, name, plant), tool_calls = list())
  })
}
