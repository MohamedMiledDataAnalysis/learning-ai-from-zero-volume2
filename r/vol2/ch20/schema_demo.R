# Chapter 20: what the model is told about one tool, written by R.
source("r/taragent/load.R")

schema <- Filter(function(s) s$`function`$name == "run_trigger_tests", tool_schemas())[[1]]
cat(prettify(to_json(schema), indent = 2))
cat(sprintf("Tools described to the model: %d\n", length(tool_schemas())))
