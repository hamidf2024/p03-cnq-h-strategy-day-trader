# Stage 13: peer-and-oil models aimed at the three goals

*2026-11-23. Owner's instruction: develop new models for CNQ that reach the
first level of the goals (G1: 1% gross per trade, WR1: 50% win rate, S1: 8 of
12 months in which the average trade makes more than 1%), using any useful
field, trained walk-forward on 2020-2023 and tested on 2024-2026, repeating
with new models until level 1 is reached, and publishing each model as it is
finished.*

## Result in one paragraph

Six models were built. **E, Peer-Fusion GBM**, is the first model in the
project to reach G1: +1.41% gross per trade over 39 trades, 60.5% win rate,
positive in each of the three test years. **J, One-a-month campaign**, reaches
level 1 on all three goals on 2024-2026: +2.24% per trade (G2), 88.6% win rate
(WR3) and 10, 12 and 9-of-11 qualifying months (S1). J's result has to be read
with its cautions (Section 6): it wins small and loses big, it was the sixth
model run on the test years in this stage, and on the training years its
choice of entry day added nothing over entering on any day.

## 1. What level 1 requires (worked out before building anything)

`src/s13_feasibility.py`, training years only. Using CNQ's real 5-day and
10-day returns, a strategy that gets the direction right with probability p:

| Direction right | Avg per 5-day trade | Months above 1% per 12 (2 trades a month) | Chance of 8 of 12 in a year |
|---|---|---|---|
| 50% | 0.0% | 4.7 | 0% |
| 55% | 0.5% | 5.2 | 0% |
| 60% | 0.9% | 5.8 | 1% |
| 70% | 1.8% | 7.0 | 14% |
| 80% | 2.6% | 8.4 | 65% |

G1 needs about 61% directional accuracy; S1 with time-based exits needs 75 to
80%. Models in this project and in the literature sit at 52 to 55%. Two
conclusions followed. First, S1 would not come from prediction accuracy alone.
Second, the S and WR goals count *how often* a trade or a month is a winner,
not how large the losses are, so the shape of the exit matters as much as the
entry. That is first-passage reasoning from physics: a profit target that is
small next to the stock's monthly swing is reached in most trades.

Also noted: in 2020-11 to 2023-12 simply buying CNQ for 5 days on any day
averaged +1.04% with 53% of months above 1%. Any long-only result on the
training years therefore had to be judged against a no-skill line, not
against zero.

## 2. Data

Local 5-minute files, consolidated feed, 2020-07-27 to 2026-11-20 (the
partial session of 11-23 dropped): CNQ, SU, CVE, IMO, XOM, CVX, the oil fund
USO and the sector fund XLE. The three vendor gap days are dropped for the
five affected stocks. Blind window for entries: 2024-01-02 to 2026-11-18, the
same as the goal scorecard. Earlier stages used the IEX feed for CNQ; Stage 13
uses the consolidated feed for prices and features.

`src/s13_lib.py` builds one row per stock per day with 57 causal features
(decision one 5-minute bar before the close; entry at the close): own returns
and volatility; overnight, intraday and last-hour moves; return gaps to the
peer basket; the stock's rolling-beta residual against peers and against oil
(a "spring" displacement); oil and sector returns; cross-sectional rank and
dispersion; calendar. The trade simulator walks the 5-minute path for targets
and stops; a bar that touches both counts as the stop, and a gap through a
level fills at the open.

## 3. The six models

All are long-only except F. Models E-H were written down before any of them
was run on 2024-2026. I and J were each designed after the previous blind
result was known, and selected on 2021-2023 only.

| Model | Idea | Field |
|---|---|---|
| E. Peer-Fusion GBM (R1) | One shallow gradient-boosted model trained on all six stocks at once (six times the labels of a CNQ-only model). Buy CNQ when its forecast is in the top 15% of its own last 120 forecasts; hold 5 days. | pooled panel ML |
| F. Peer-and-oil spring (R2) | CNQ stretched away from its peers and from oil (average of two residual z-scores beyond 1) and turning back: long below, short above; hold 5 days. | physics, relative value |
| G. Fusion ensemble (R3) | E's model, a ridge model and a cross-asset transformer (40 days of 8 assets), trailing ranks averaged; hold 5 days. | model combination |
| H. Peer-Fusion, target and stop (R4) | E's signal with a 5% target, 5% stop, 10-day limit. | exits |
| I. First-passage campaign (R5) | E's model with a lower bar (above its own median), 2% target, 20-day limit, no stop. | first-passage exits |
| J. One-a-month campaign (R6) | One trade per calendar month, on the first day E's model is above its own median; 4% target, 60-day limit, no stop; trades may overlap. | first-passage exits |

Entry thresholds are trailing ranks of the model's own out-of-sample
forecasts, so the number of trades stays steady from year to year. Stage 12's
fixed training-quantile thresholds had produced 25 trades where 72 were
expected.

## 4. Walk-forward validation (2021, 2022, 2023; labels purged)

Selection rule for E-H, fixed in advance: among settings with at least 6
trades in every validation year, the best worst-year excess over the no-skill
line (entering on every day with the same exit). For I and J: settings that
reach G1, WR1 and S1 in every validation year, then the best worst-year
excess.

| Model | Setting chosen | Trades | G | WR | S by year | Excess | Worst-year excess |
|---|---|---|---|---|---|---|---|
| E | 5 days, long | 37 | +1.26% | 59.5% | 3, 4, 8 | +0.50% | -0.25% |
| F | 5 days, long and short, k=1 | 28 | +1.14% | 48.1% | 2, 3, 5 | +1.34% | +1.06% |
| G | 5 days, long | 30 | +0.05% | 56.7% | 2, 3, 7 | -0.67% | -1.71% |
| H | target 5, stop 5 | 40 | +1.74% | 65.0% | 3, 6, 7 | +1.38% | +0.46% |
| I | rank 0.5, target 2, 20 days | 89 | +1.55% | 95.5% | 9, 11, 8 | +0.46% | +0.33% |
| J | rank 0.5, target 4, 60 days | 32 | +2.80% | 87.5% | 9, 10, 9 of 10 | -0.05% | -0.97% |

Out-of-fold rank correlation with the next 5-day return: gradient boosting
0.059, ridge 0.062, transformer 0.076. One of 36 settings passed the level-1
gate for I; two of 18 passed for J. J's excess on the training years was
zero: its validated performance came from the exit rule and the rising
market, not from its choice of day.

## 5. Test on 2024-2026 (one run per model, logged)

| Model | Trades | G | 95% range | WR | S by year | Excess | Without top 2 | Worst trade | Levels |
|---|---|---|---|---|---|---|---|---|---|
| E | 39 | **+1.41%** | +0.1 to +2.8 | 60.5% | 6, 4, 4 | +1.06% | +0.93% | -7.1% | G1, WR1 |
| F | 56 | +0.43% | -0.7 to +1.6 | 50.9% | 3, 6, 4 | +0.43% | +0.01% | -8.0% | WR1 |
| G | 38 | +0.81% | -0.5 to +2.1 | 56.8% | 1, 3, 3 | +0.48% | +0.43% | -7.5% | WR1 |
| H | 38 | +0.85% | -0.6 to +2.3 | 55.3% | 6, 3, 2 | +0.71% | +0.59% | -5.0% | WR1 |
| I | 78 | +0.59% | -0.4 to +1.4 | 84.6% | 6, 7, 9 | +0.25% | +0.54% | -17.3% | WR3 |
| J | 35 | **+2.24%** | +0.3 to +3.9 | 88.6% | 10, 12, 9 of 11 | +1.21% | +2.09% | -17.3% | G2, WR3, S1 |

E by year: 15 trades +1.45%, 11 trades +1.55%, 13 trades +1.24%. J by year:
12 trades +0.88% (83% wins), 12 trades +4.13% (100%), 11 trades +1.67% (82%).
After a 1 cent per share cost E keeps +1.38% and J +2.21%.

`verify` reproduces all six results exactly from the frozen artefacts. The
run log (`stage13_BLIND_RUN_LOG.json`) records each run and refuses a second.

## 6. How to read J

- 31 of 35 trades reached the +4% target (median 9 trading days). The four
  that did not were held 60 days with no stop: -12.4%, -17.0%, -0.4%, and one
  still open at -17.3% when the data ended.
- Trades overlap: up to three open at once, two or more on 17% of days. The
  $1,000-per-trade figures are per trade, not per account.
- Entering on any day with J's exit rule averaged about +1.0% per trade in
  2024-2026 (-1.0%, +2.6%, +1.6% by year). J's entry day added about +1.2% on
  the test years and nothing on the training years.
- S counts a trade in its entry month. A trade entered in March that reaches
  +4% in May makes March count.
- J is the sixth Stage 13 model run on 2024-2026 and the sixteenth
  walk-forward model overall. It was designed after I's blind result. A level
  reached this way is weaker evidence than a single pre-registered run.
- A sustained fall is the failure case: with no stop, a new position each
  month and a 60-day limit, three positions can be under water together. The
  data begins in July 2020, after the 2020 oil collapse.

## 7. What is and is not established

- Established: pooling the six oil stocks gave a forecasting model whose top
  forecasts earned more than 1% per 5-day trade on unseen years, in each year
  (E). That is the first result in this project whose 95% range excludes zero.
- Established: with a profit-target exit and one trade a month, the win-rate
  and steadiness goals are reachable (J); they depend more on the exit rule
  than on forecasting.
- Not established: that J's average will stay above 1% when CNQ falls for a
  year, or that its entry rule adds value. Only new data can show that.
- The combination with a transformer (G) did not beat the single pooled model
  (E), as in Stage 12.

## 8. Next steps

1. Forward-test E and J exactly as frozen on trades after 2026-11-20. Do not
   retune either on 2024-2026.
2. Decide with the owner whether J's risk shape is acceptable, and whether
   the goals should add a limit on the worst trade or on capital at work.
3. Test J's exit rule with E's stricter entry and with a wide catastrophe
   stop, on 2020-2023 only, then on new data.

## 9. Addendum, same day: the owner's 5% worst-trade rule, models K and L

After seeing model J, the owner added a risk rule: no trade may lose more
than 5%, so every model carries a 5% stop, and levels count only inside the
rule. Two more models were run once each on 2024-2026 (looks seven and eight
of this stage):

| Model | Idea | Validation (G / WR / S) | Test: trades | G | WR | S by year | Worst trade | Levels |
|---|---|---|---|---|---|---|---|---|
| K. One-a-month, 5% stop (R7) | J's design re-selected with a 5% stop: 2% target, 20 days | +0.33% / 75.8% / 8, 9, 8 (no setting passed the level-1 gate) | 35 | +0.02% | 71.4% | 8, 10, 7 of 11 | -5.4% | WR2 |
| L. Peer-Fusion GBM, 5% stop (R8) | Model E unchanged plus a 5% stop; nothing selected | +1.09% / 56.4% / 2, 5, 7 | 39 | +1.05% | 60.5% | 6, 4, 3 | -5.0% | G1, WR1 |

Inside the rule no model reaches level 1 on all three goals. L keeps G1 and
WR1 (its 95% range is -0.4% to +2.6%, so it now includes zero). K keeps the
shape that S and WR reward but its average falls to zero: with the stop at
5% and the target at 2%, ten stops cancel twenty-five targets.

The cost of the stop on the training years, for J's design: G +0.57% at 5%,
+0.62% at 8%, +0.93% at 10%, +1.44% at 15%, +2.80% with none; S 7/7/6 at 5%
rising to 9/10/9 with none. CNQ moves about 5% in a normal week, so a 5% stop
is hit by ordinary swings and removes the recovery that the target design
relies on.

## Code and results

`src/s13_lib.py`, `src/s13_feasibility.py`, `src/stage13_peer_fusion.py`
(modes `walkforward`, `round5`, `round6`, `round7`, `round8`, `blind`, `verify`);
`results/experiments/stage13_feasibility.json`,
`stage13_walkforward_results.json`, `stage13_frozen.pkl`,
`stage13_frozen_R5.pkl` to `stage13_frozen_R8.pkl`,
`stage13_BLIND_RUN_LOG.json`, `stage13_blind_results.json`,
`stage13_blind_trades.csv` (dates and returns, no prices). The priced trade
list and the panel cache stay in the local folder only.

## Sources

- Lopez de Prado, M. (2018), *Advances in Financial Machine Learning*
  (triple-barrier exits, meta-labelling, purged validation).
- Hudson & Thames, [Does meta-labeling add to signal efficacy?](https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy/)
- Gu, Kelly & Xiu (2020), "Empirical Asset Pricing via Machine Learning",
  *Review of Financial Studies* (pooled panel models; trees and shallow nets).
- Driesprong, Jacobsen & Maat (2008), "Striking oil: Another puzzle?",
  *Journal of Financial Economics* (oil returns and later stock returns).
- Pollet, [Predicting Asset Returns with Expected Oil Price Changes](https://www.econbiz.de/Record/predicting-asset-returns-with-expected-oil-price-changes-pollet-joshua-matthew/10012736441)
- Hong, Torous & Valkanov (2007), "Do industries lead stock markets?",
  *Journal of Financial Economics*.
- Redner, S. (2001), *A Guide to First-Passage Processes*.
- Bailey & Lopez de Prado (2014), [The Deflated Sharpe Ratio](https://papers.ssrn.com/abstract=2460551)
  (why repeated tests on the same data inflate results).
