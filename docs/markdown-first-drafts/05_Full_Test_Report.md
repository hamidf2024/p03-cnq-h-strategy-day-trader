**STATUS: TEMPLATE — no backtest has been run yet.** Duplicate this doc (or replace its content) once each test run in `04_Test_Protocol.md` completes, so results accumulate as a record rather than overwriting each other.

## Test Run Identification
- **Date of run:**
- **Strategy version tested** (Baseline / V2 / V3 / V4 / V5 / Final candidate):
- **Rule delta from previous version** (link to the matching entry in `06_Lessons_Learned.md`):
- **Dataset / split used** (development / validation / out-of-sample / specific walk-forward fold):
- **Code/backtester version or commit reference:**

## Executive Summary
*(2–3 sentences: did this version help, hurt, or was it inconclusive relative to baseline? Accept or reject?)*

## Results Table

| Metric | This run | Baseline | Δ |
|---|---|---|---|
| Number of trades | | | |
| Win rate | | | |
| Average win | | | |
| Average loss | | | |
| Profit factor | | | |
| Expectancy per trade | | | |
| Net P&L | | | |
| Max drawdown | | | |
| Longest losing streak | | | |

## Walk-Forward Fold Results
*(one row per fold, per the schedule in `04_Test_Protocol.md`)*

| Fold | Train window | Test window | Trades | Win rate | Net P&L | Max DD |
|---|---|---|---|---|---|---|
| 1 | | | | | | |
| 2 | | | | | | |

## Rule Attribution
*(which specific rule changes drove the difference vs. baseline — isolate one variable at a time per Stage 5)*

## Rejected-Setup Audit Sample
*(spot-check a handful of NO_TRADE decisions and confirm the reasoning was correct — pull directly from the decision audit records described in `02_Core_Trade_Strategy_Rules.md`)*

## Out-of-Sample Result (Stage 6 only — fill in once, do not re-run)

## Stability / Regime Notes
*(performance by week/month, and any market-regime observations — trending vs. choppy days, volatility spikes, etc.)*

## Conclusion & Recommendation
- [ ] Accept — becomes new baseline
- [ ] Reject — revert to previous version
- [ ] Inconclusive — needs more data / a different test

**Reasoning:**
