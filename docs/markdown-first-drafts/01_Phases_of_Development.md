## Phase 1 — Research, Testing & Development

**Objective:** turn the current trading knowledge into a precise, testable strategy, then use historical data to understand what works, what doesn't, and why. Do not assume any current rule is optimal — treat the current rules (`02_Core_Trade_Strategy_Rules.md`) as the baseline strategy to be tested, not a foregone conclusion.

### Stage 1 — Formalize the rules
Convert subjective language ("strong green candle," "long lower wick," "zone is formed," "price action stays constructive," "large opening dump") into objective, measurable definitions before backtesting starts. Candidate variables for "strong green candle": body size, range, body/range ratio, close-location, relative size vs. previous N candles, relative size vs. the previous red candle. Don't lock in thresholds yet — that's Stage 5.

### Stage 2 — Build the historical data engine
Ingest and clean the historical 5-minute CNQ data (see `03_Data_Folder.md`), build the regular-session builder, and establish the zone-detection engine described in `02_Core_Trade_Strategy_Rules.md`.

### Stage 3 — Build the walk-forward backtester
Implement the pipeline below so every decision uses only information available at that historical moment (see `04_Test_Protocol.md` for full methodology):

```
Historical Data → Data Cleaning → Session Builder → Zone Detection Engine
→ Confirmation Engine → Entry Engine → Risk Manager → Exit Engine
→ Trade Ledger → Performance Analyzer → Research Dashboard
```

### Stage 4 — Analyze the strategy
Test the **baseline** strategy first, unmodified, and measure: number of trades, wins, losses, breakeven trades, win rate, average win, average loss, profit factor, expectancy, maximum drawdown, net P&L.

### Stage 5 — Improve and optimize
Research proceeds in versions, changing one concept at a time:

1. **Version 1 — Baseline.** Current rules, no optimization.
2. **Version 2 — Rule investigation.** E.g. test strong-green body/range threshold at 70/75/80/85%.
3. **Version 3 — Zone research.** Zone width, second-low/second-high definitions, horizontal-base duration, number of tests, distance between tests.
4. **Version 4 — Entry research.** Strong-green definition, previous-red comparison, wick rejection, HOD breakout requirement, triangle rule.
5. **Version 5 — Risk research.** 0.10/0.20 vs 0.15/0.30, alternative stop placement, breakeven timing, higher-zone exits.

Every change must be logged in `06_Lessons_Learned.md` as a research-log entry (hypothesis, rule changed, reason, dataset, results, comparison to baseline, statistical impact, accept/reject).

### Stage 6 — Out-of-sample validation
Validate the final candidate strategy on data never touched during development (see `04_Test_Protocol.md`).

## Phase 2 — Automated Trading

Only begins after Phase 1 passes historical, walk-forward, and out-of-sample validation. The live system must use the **same strategy logic** as the validated backtester — only the data and execution layer changes. This prevents the classic failure mode where the backtest strategy and the live strategy silently diverge.

### Architecture
```
Live CNQ 5-Minute Data → Market Data → Zone Engine → Confirmation Engine
→ Entry Engine → Risk Manager → Order Manager → Broker API → Position
→ Trade Monitoring → Audit Logger
```

### Required safety controls (before any live trading)
Maximum daily loss; maximum trades per day; one-trade-at-a-time enforcement; position-size limits; duplicate-order protection; order timeout; broker connection monitoring; data-feed monitoring; emergency flatten control; end-of-day forced flatten; trading-session validation; clock/time-zone validation; full trade and order/rejection logging. Guiding principle: **if the system is uncertain, it should not trade** — a missed trade is preferable to an incorrect one.

### Gates (must pass in order)
1. Historical backtest passes.
2. Out-of-sample testing passes.
3. Paper trading passes.
4. Shadow/live monitoring passes.
5. Very small live position.
6. Gradual scaling.
