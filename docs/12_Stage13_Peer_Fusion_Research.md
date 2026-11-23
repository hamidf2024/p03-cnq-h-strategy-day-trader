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

## 10. Addendum: two risk levels (5% and 15%), model M

The owner then asked for 5% and 15% to be considered together. Levels now
count inside the 15% limit, and every model is also marked against 5%. One
more model was run once on 2024-2026 (look nine of this stage): **M, model J
unchanged with a 15% stop** (one setting, nothing selected; validation
+1.44%, 84.4%, S 9 / 9 / 9 of 10, with a losing year in 2022).

Test result: 35 trades, **+1.85% per trade (G1), 88.6% win rate (WR3), S 10 /
12 / 9 of 11 (S1)**, worst trade -15.7% (a gap through the stop), 95% range
-0.4% to +3.5%, +1.82% after the 1 cent cost. By year: +0.82%, +4.13%,
+0.48%. Exits: 31 targets, 4 stops. M reaches level 1 on all three goals
inside the 15% limit; nothing does inside 5%. The cautions listed for J in
Section 6 apply to M, except that its losses are capped near 15%.

## 11. Addendum: fourth goal GM and model N

The owner added a fourth goal, GM (months whose trades add up to 5% or more;
8 / 10 / 12 of 12), and asked for a model at level 1 on all four goals.
**Model N (R10)**: two trades a month, one in each half, on the first day the
Peer-Fusion model is at least neutral; +6% target, 15% stop, 60-day limit.
Selection used 2021-2023 only, with 2024-2026 removed from the data
(`S13_CUTOFF`); 2 of 32 settings reached level 1 on all four goals in every
training year, both at the threshold on the month goals.

Test result, one run (look ten of this stage, twentieth overall): 68 trades,
+0.74% per trade (95% range -1.3% to +2.6%), 70.6% win rate, S 6 / 8 / 5,
GM 6 / 8 / 5, 45 targets, 12 stops and 11 time exits, year totals +14.9%,
+55.4%, -20.0%, up to five trades open at once. **Not level 1 on G, S or
GM.** Doubling the trades per month doubled the stops in falling stretches
(late 2024, spring 2026), and a month fails both month goals as soon as one
of its two trades is stopped. A passing margin of zero on the training years
was not a margin.

## 12. Addendum: a stricter gate after N, and a search that spent no test run

After N the training gate was tightened and written into the code before
anything was computed (`src/s13_ladder_gate_search.py`, run with the test
years removed from the data):

- **A.** On CNQ, in each of 2021, 2022 and 2023, S and GM must each beat the
  level-1 count by at least one month; over the three years G at least 1.25%
  and win rate at least 55%.
- **B.** The same exit and second-entry rule, with a plain first-day-of-month
  entry, must reach S1 and GM1 in at least 14 of the 18 stock-years of the
  six stocks (CNQ, SU, CVE, IMO, XOM, CVX), with at least 1.0% per trade
  across all six.
- **C.** A second trade must be a separate decision on a later day.

Family searched: a monthly campaign whose second entry is none, five or ten
sessions later, on a dip of 2% or 3%, or on a rise of 1% or 2%; targets 2.6,
3, 4 and 5.5%; stops 10 and 15%; time limits 40 and 60 sessions. 112 eligible
settings.

**Result: none of the 112 clears the gate. No model was frozen and no run on
2024-2026 was made; the count of looks stays at twenty.** No eligible setting
cleared part A at all (best worst-year margin: zero months); two cleared part
B. The closest were a second entry on a dip of 2% or 3% with a +5.5% target
(training G +2.8%, S 8 / 9 / 10, GM 8 / 9 / 9, margin zero in 2021).

One ineligible setting clears both parts: **two $1,000 trades opened on the
same day** with model M's exit (+4% target, 15% stop, 60 sessions). That is
model M with twice the money on each entry, not a new model: G, WR and S are
M's, and GM passes only because the month's total is a sum over trades, so
two trades of +4% add up to 8%. Read off M's already-published 2024-2026
months, it would score GM 10 / 12 / 9 of 11. That is arithmetic on a known
result and adds no evidence. Whether trades opened together should count
separately towards GM is a question about the goal, put to the owner; it is
not counted here.

What this says: on these data, exits and entry spacing cannot lift the month
goals above the level-1 line with room to spare, even in three rising years.
Reaching level 1 on all four goals with a margin needs a better forecast of
the month ahead, which means new information (Section 8), not another
arrangement of the same trades.

## 13. Addendum: stops from 1% to 15% (owner's request), to find the best size

The owner asked that the next model consider any stop from 1% to 15%.
`src/s13_stop_range_search.py` repeats the Section 12 search with ten stop
sizes (1, 2, 3, 4, 5, 6, 8, 10, 12, 15%), six targets (2.6 to 9%), three time
limits (20, 40, 60 sessions) and nine entry patterns, one of them new: buying
again at the close after a stop-out, up to two or three trades in the month.
1,620 eligible settings; training years only, test years removed; same gate
as Section 12.

One trade a month, +5.5% target, 60 sessions, CNQ, 2021-2023 (32 trades):

| Stop | G per trade | Win rate | Stopped out | S 2021/22/23 | GM 2021/22/23 |
|---|---|---|---|---|---|
| 1% | +0.95% | 31% | 22 | 3 / 4 / 3 | 3 / 4 / 3 |
| 2% | +1.01% | 41% | 19 | 5 / 4 / 4 | 5 / 4 / 4 |
| 3% | +0.96% | 47% | 17 | 5 / 5 / 5 | 5 / 5 / 5 |
| 4% | +0.70% | 50% | 16 | 5 / 6 / 5 | 5 / 6 / 5 |
| 5% | +0.86% | 56% | 14 | 5 / 7 / 6 | 5 / 7 / 6 |
| 6% | +0.49% | 56% | 14 | 5 / 7 / 6 | 5 / 7 / 6 |
| 8% | +0.92% | 66% | 11 | 5 / 8 / 8 | 5 / 8 / 8 |
| 10% | +1.68% | 75% | 8 | 7 / 9 / 8 | 7 / 9 / 8 |
| 12% | +1.65% | 78% | 7 | 7 / 9 / 9 | 7 / 9 / 9 |
| 15% | +2.08% | 81% | 5 | 8 / 9 / 9 | 8 / 9 / 9 |

(Level 1 needs 8 / 8 / 7 months.)

**Result: the best stop on the training years is 15%, the widest allowed.
None of the 1,620 settings clears the gate; no run on 2024-2026 was made
(still twenty looks).** The best worst-year margin on the month goals at each
stop size was -4 months at 1%, -3 from 2% to 8%, -1 at 10% and 12%, and 0 at
15%. With stops of 1% to 3% almost no setting keeps a 50% win rate. Buying
again after a stop did not help: a month with one stopped trade and one
winner rarely averages above 1% per trade. Stops of 4% and 5% can reach G1
and WR1 together (for example a second entry on a 2% dip, +5.5% target, 20
sessions: +1.4% to +1.5%, 58% to 61%), which is what model L already does on
the test years, but not the month goals.

Why: CNQ's ordinary day-to-day swing is about 2%, so a stop of a few percent
is inside the noise and sells trades that would have recovered. The caution
is the same as before: 2021-2023 were rising years, and in a falling year a
wide stop makes each loss larger.

## 14. Addendum: the same-time rule, and model O (two buys at different times)

**Owner's rule, 2026-11-23.** Trades opened at exactly the same time count as
one trade; trades opened at different times count separately, even on the
same day. It is in the charter, `docs/07` and the scoring code
(`merge_same_time`). Re-scoring every model with the rule changed nothing:
no model so far opens two trades at the same moment.

**Model O** (`src/stage13_two_buys.py`). Model M's signal and exit, unchanged
(first day of the month the Peer-Fusion model is at least neutral; +4%
target, 15% stop, 60 sessions), with two $1,000 buys at different times. Six
fixed buy patterns were the only thing selected. "At 10:00" means the close
of the 5-minute bar ending at 10:00; two buys that fall on the same bar are
the same time and count once.

Training years only, test years removed, same gate as Sections 12 and 13:

| Buys | Trades | G | Win rate | S 2021/22/23 | GM 2021/22/23 | Spare months | Peer stock-years |
|---|---|---|---|---|---|---|---|
| signal-day close, next day 10:00 | 64 | +1.72% | 85.9% | 8 / 9 / 10 | 8 / 9 / 9 | 0 | 15 of 18 |
| signal-day close, next day 13:00 | 64 | +1.23% | 84.4% | 8 / 8 / 10 | 8 / 8 / 9 | 0 | 15 of 18 |
| next day 09:35 and close | 64 | +1.85% | 87.5% | 8 / 9 / 10 | 8 / 9 / 10 | 0 | 16 of 18 |
| next day 10:00 and 13:00 | 64 | +1.51% | 85.9% | 8 / 9 / 10 | 8 / 9 / 10 | 0 | 17 of 18 |
| next day 10:00 and close | 64 | +1.85% | 87.5% | 8 / 10 / 10 | 8 / 10 / 10 | 0 | 16 of 18 |
| next day 13:00 and close | 64 | +1.36% | 85.9% | 8 / 9 / 10 | 8 / 9 / 10 | 0 | 16 of 18 |

(Level 1 needs 8 / 8 / 7 months; the gate needs one more in every year.)

**Result: every pattern reaches level 1 on all four goals on the training
years and holds on the peer stocks, but none has the spare month the gate
requires: 2021 gives exactly 8 of 12 on both month goals for all six. Nothing
was frozen and no run on 2024-2026 was made (still twenty looks).**

This is the same position model N was in before its test run: level 1 on the
training years with nothing to spare. The gate was written after N for this
case, and it is applied here even though model M's known test result makes a
good outcome for O likely. That likelihood is the reason for caution, not
against it: O is M twice, its two buys usually win or lose together, it puts
$2,000 at risk on each monthly entry, and a run would show little that M's
result does not already show. Whether to run it anyway, marked as run at the
owner's request without passing the gate, is the owner's decision.

## Code and results

`src/s13_lib.py`, `src/s13_feasibility.py`, `src/s13_ladder_gate_search.py`
(the stricter gate and the 112-setting search, results in
`results/experiments/stage13_round11_gate_search.json`), `src/s13_stop_range_search.py`
(stops from 1% to 15%, `stage13_round12_stop_range_search.json`), `src/stage13_two_buys.py`
(model O, `stage13_round13_two_buys_selection.json`), `src/stage13_peer_fusion.py`
(modes `walkforward`, `round5`, `round6`, `round7` to `round10`, `blind`, `verify`);
`results/experiments/stage13_feasibility.json`,
`stage13_walkforward_results.json`, `stage13_frozen.pkl`,
`stage13_frozen_R5.pkl` to `stage13_frozen_R10.pkl`,
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
