## Guiding Principle
Never optimize solely for historical net profit. Every strategy modification must be documented as a research-log entry (see `06_Lessons_Learned.md`): hypothesis, rule changed, reason for change, dataset used, results, comparison with baseline, statistical impact, and an explicit accept/reject decision. Never silently change the strategy.

## Metrics Tracked On Every Test Run
Net profit; profit factor (gross profits / gross losses); expectancy per trade = (win rate × average win) − (loss rate × average loss); win rate; average win; average loss; maximum drawdown; number of trades; R-multiple distribution; consecutive losses; monthly/weekly stability; performance by market regime; out-of-sample performance. Win rate is never the primary target — a high win rate with a poor win/loss ratio (e.g. 80% wins at $5 avg vs $25 avg loss) can be worse than a lower win rate with a strong ratio.

## Dataset Splits
With the current ~3-month / 60-trading-day dataset (`03_Data_Folder.md`), split as:

- **Development** — used to formalize and tune rules (Stages 1, 4, 5).
- **Validation** — used to choose among reasonable rule variations, not to pick the single best-fitting parameter.
- **Out-of-sample** — never touched during development; used once, at the end, in Stage 6.

Because the dataset is thin, prefer **walk-forward folds** over a single static split — this is much closer to how the strategy would actually behave live.

### Suggested walk-forward schedule for the current data (2026-05-20 → 2026-08-14)
Since the sample is only ~13 weeks, use short rolling windows rather than the multi-month folds a longer dataset would allow:

```
Fold 1 — Train: May 20 – Jun 16 (4 wks)   Test: Jun 17 – Jun 23 (1 wk)
Fold 2 — Train: May 27 – Jun 23 (4 wks)   Test: Jun 24 – Jun 30 (1 wk)
Fold 3 — Train: Jun 03 – Jun 30 (4 wks)   Test: Jul 01 – Jul 07 (1 wk)
Fold 4 — Train: Jun 10 – Jul 07 (4 wks)   Test: Jul 08 – Jul 14 (1 wk)
Fold 5 — Train: Jun 17 – Jul 14 (4 wks)   Test: Jul 15 – Jul 21 (1 wk)
Fold 6 — Train: Jun 24 – Jul 21 (4 wks)   Test: Jul 22 – Jul 28 (1 wk)
Fold 7 — Train: Jul 01 – Jul 28 (4 wks)   Test: Jul 29 – Aug 04 (1 wk)
Fold 8 — Train: Jul 08 – Aug 04 (4 wks)   Test: Aug 05 – Aug 11 (1 wk)
```
Reserve the final ~2 weeks (Aug 03–Aug 14, adjust once the fold boundaries are locked) as the untouched out-of-sample block for Stage 6, not used in any fold above. Revisit this schedule once more historical data is added per the sufficiency note in `03_Data_Folder.md`.

## Baseline Test (Stage 4)
Run `02_Core_Trade_Strategy_Rules.md` exactly as written, unmodified, across the development split. Record every metric above. This becomes the number every later version is compared against.

## Rule-Investigation Tests (Stage 5, Versions 2–5)
Change **one concept at a time**, never several at once, so attribution stays clean:
- Version 2 — confirmation thresholds (e.g. strong-green body/range % at 70/75/80/85).
- Version 3 — zone definition (width, second-low/second-high thresholds, horizontal-base duration).
- Version 4 — entry logic (strong-green definition, previous-red comparison basis, wick rejection, HOD breakout requirement).
- Version 5 — risk parameters (0.10/0.20 vs 0.15/0.30, wide-day threshold, breakeven timing, higher-zone exit behavior).

## Overfitting Controls
Do not search for the single parameter combination with the highest historical profit. Prefer simple rules, stable parameter ranges, robust performance, and a logical market rationale over a narrow optimum. If a parameter only performs at one very specific value, treat that as an overfitting warning sign, not a discovery.

## Out-of-Sample Validation (Stage 6)
Run the final candidate strategy — untouched since Version 5 was locked — once against the reserved out-of-sample block. Report results honestly in `05_Full_Test_Report.md` regardless of outcome; do not iterate further against the out-of-sample data (doing so converts it back into a validation set and defeats its purpose).

## Phase 2 Readiness Gates
Testing is not "done" until, in order: historical backtest passes → out-of-sample testing passes → paper trading passes → shadow/live monitoring passes → small live position proves out → gradual scaling begins. See `01_Phases_of_Development.md` for full detail on each gate.
