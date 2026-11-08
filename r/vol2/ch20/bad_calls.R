# Chapter 20: what the model reads back when its tool call is wrong (R registry).
source("r/taragent/load.R")

cat(call_tool("run_trigger_test", list(period = 10)), "\n")
cat(call_tool("run_trigger_tests", list(month = 10)), "\n")
cat(call_tool("run_trigger_tests", list(period = 13)), "\n")
cat(substr(call_tool("run_trigger_tests", "{period: 10}"), 1, 80), "...\n")
