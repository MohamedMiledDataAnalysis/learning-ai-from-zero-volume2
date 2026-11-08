# Chapter 24: a plan that forgets three checks is completed from the analyst's checklist.
# The "model" is a rule brain that returns a hand-written incomplete plan, so the example is reproducible.
source("r/taragent/load.R")

incomplete <- '[{"tool": "run_trigger_tests", "arguments": {"period": 10}, "why": "check the triggers"}]'
brain <- rule_brain(function(memory) list(content = incomplete, tool_calls = list()))
folder <- tempfile()
r <- run_surveillance(10, plan_source = "model", brain = brain, memory_dir = file.path(folder, "m"),
                      out_dir = file.path(folder, "o"), approve = FALSE)
cat("Missing from the plan:\n")
for (m in r$missing_from_plan) cat("  -", m$tool, if (is.null(m$arguments)) "{}" else to_json(m$arguments), "\n")
unlink(folder, recursive = TRUE)
