"""Reference solution, chapter 3 practical task: a plan that passes the checklist with nothing missing."""


def my_plan(period):
    return [
        {"tool": "run_trigger_tests", "arguments": {"period": period}, "why": "triggers and payment mode"},
        {"tool": "stratify_pool", "arguments": {"by": "region", "measure": "balance_90plus", "period": period},
         "why": "where the 90+ arrears are"},
        {"tool": "stratify_pool", "arguments": {"by": "region", "measure": "balance", "period": period},
         "why": "pool by region, for the self-check"},
        {"tool": "search_prospectus", "arguments": {"query": "90+ day arrears ratio limit"},
         "why": "quote the limit with its page"},
        {"tool": "draft_surveillance_note", "arguments": {"period": period}, "why": "the monthly note"},
    ]
