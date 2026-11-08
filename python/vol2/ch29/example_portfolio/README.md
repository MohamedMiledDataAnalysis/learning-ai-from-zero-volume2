# Pool factor and prepayment speed tool for an auto ABS agent

## Problem
Surveillance analysts track how fast a securitised pool repays. I added a tool that gives the pool factor and
the prepayment speed (SMM and CPR) for any month, so the agent can answer these questions from data.

## Data
The fictional deal pack *Thames Auto Receivables 2026-1* from the companion repository of
*Learning AI from Zero*: 12 monthly investor reports, 5,000 loans.

## How to run
```bash
pip install -r requirements.txt
python -m pytest -q
```

## Results
The tool returns the pool factor, SMM and CPR for periods 1 to 12 and passes the course's grading script
(30/30).

## Limits
Prepayment speed is computed on one month's data; it is a measurement, not a forecast.
