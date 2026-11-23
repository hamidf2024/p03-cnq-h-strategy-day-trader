# Stage 12: "Field-Fusion Swing" -- physics, control engineering, information theory, ML and a transformer, tested against the >1% per trade target

*Added 2026-11-23, at the owner's direction: "through deep research and
learning whatever you have done so far ... develop new and unique and
innovative model and trading method for CNQ that can reach our major goal
which is more than 1 percent gross per trade averagely for 2024 to 2026. You
can consider different ML transformers, or any useful ML methods, or using
other fields like famous and latest mathematics, physics, engineering
formula ... use the same approach for training data, 2020-2023 walk forward
training and then testing on 2024-2026."*

## 0. Result first

**Target 1 (more than 1% average gross per trade, blind 2024-2026) was not
met.** Four candidate models were built on 2020-2023 only, frozen, and run on
2024-2026 exactly once:

| Candidate (all multi-day, long-only, 5-day hold) | Blind trades | **Avg gross %/trade** | Win rate | Profit factor | Excess over random entry | Verdict |
|---|---|---|---|---|---|---|
| **A. Spring-release** (physics rule) -- *the model selected by walk-forward validation* | 21 | **-0.70%** | 38.1% | 0.71 | -1.23% | failed |
| **B. Field-Fusion GBM** (ML over 33 cross-field features) | 25 | **+0.99%** | 48.0% | 1.65 | +0.63% | just under target, not statistically significant |
| **C. Transformer probe** (self-supervised PatchTST-style encoder) | 51 | **+0.64%** | 51.0% | 1.46 | +0.17% | below target |
| **D. Fusion gate** (A's event, vetoed by B's model) | 19 | **+0.52%** | 52.6% | 1.32 | +0.05% | below target |

Read plainly:

- The model the validation procedure chose (A) **lost money on blind data**.
  It had looked the strongest of the four on 2021-2023 (27 trades, +3.12% per
  trade, 78% winners). That did not carry over.
- The machine-learning model (B) averaged **+0.99% per trade** -- about 49
  times V7.1's 0.0204% and the closest any method in this project has come --
  but it is below 1%, it rests on 25 trades, and two of those trades (+13.1%
  and +10.3%) supply nearly all of it: without them the other 23 average
  +0.06%. Its 95% bootstrap interval is -0.88% to +2.94%. That is not evidence
  of a reliable 1% edge.
- Part of every long multi-day result is simply CNQ rising: a randomly timed
  5-day long position averaged +0.35% over 2024-2026. "Excess" in the table
  is what is left after subtracting that.
- The transformer did not beat the simpler tree model, in line with the
  published evidence reviewed in Section 2.

One finding is genuinely new and useful: B's ranking of days held up on blind
data (rank correlation between its prediction and the next 5-day return +0.12
over the 697 blind days it scored; the top fifth of its predictions was followed by an
average +1.32% 5-day return, the bottom fifth by -0.35%). That is a real lead
for the next stage, not a result.

## 1. What was available

Only CNQ's own 5-minute bars (`data/raw/CNQ_5min_20200727_to_20261118.csv`,
117,169 bars, 1,584 days). Peer stocks (SU, CVE, IMO, XOM, CVX) and crude-oil
prices would be the natural extra inputs for an energy producer, but no
market-data host was reachable from the research environment, so Stage 12 is
single-symbol. This matters and is picked up again in Section 9.

Carried over from earlier stages (`08_ML_and_Method_Development_Lessons.md`):

- Stage 11 showed that a same-day trade cannot average >1% on CNQ (its daily
  range is ~2.0-2.4%), so every Stage 12 candidate holds for several days.
- Walk-forward selection inside 2020-2023, freeze, one blind run per year.
- Small grids stated up front; a minimum trade floor; reject anything that
  lives in one or two trades.
- Persist the code and regression-check every build.

## 2. Deep research: what other fields and the ML literature offer

| Field | Idea | What the literature says | How Stage 12 used it |
|---|---|---|---|
| Machine learning -- transformers | PatchTST-style encoders; pretrained time-series foundation models (Chronos, TimesFM, Moirai) | A 2025 study on 94 countries of daily returns found zero-shot foundation models *below* tree models (out-of-sample R2 of -1.37% and -2.80% for the large Chronos and TimesFM), with CatBoost the best benchmark; pretraining on financial data helped but still trailed [1]. A 2026 preregistered test on index futures found 0 of 160 model/horizon cells beating "no change" [2]. A 2026 five-stock study found small, sparse gains and no trading alpha [3]. | Candidate C: a small encoder pretrained on CNQ's own 5-minute bars (self-supervised, so it learns from 62,000 bars instead of 860 labels), frozen, with a linear probe. Tested honestly against a tree model rather than assumed to win. Pretrained foundation models could not be downloaded here. |
| Machine learning -- labelling | Meta-labelling and triple-barrier labels (Lopez de Prado) | A second model decides whether to act on a primary signal; reported gains are mainly in precision / risk-adjusted terms [4]. | Candidate D (B's model as a veto on A's event). B itself labels *every day* rather than only event days, to get ~800 training labels instead of ~40. |
| Stochastic calculus / physics | Ornstein-Uhlenbeck mean reversion, optimal entry and exit | Leung & Li: the optimal entry region is a bounded band *above* the stop level -- it is optimal to wait rather than buy while the price is still near its stop [5]. | The "release" condition in candidate A (do not buy while the stretch is still growing). OU half-life and expected reversion are features in B. |
| Control engineering | Kalman filter (state estimation) | Standard tool for a noisy, drifting level. | Causal local-linear-trend filter gives an equilibrium price and its velocity; the displacement from it is the "stretch" used by A and B. |
| Statistical physics / information theory | Hurst exponent, permutation entropy | A 1,800-stock study found a Hurst regime switch selected a risk level rather than raising returns [6]. | Used only as features, never as a hard filter. |
| Rough-path mathematics | Path signatures (iterated integrals) | A compact, order-aware summary of a path; used to classify data streams [7]. | Level-2 signature terms (Levy areas) of the intraday price/volume/time path as features. |
| Market microstructure | Overnight versus intraday returns | Momentum and short-term reversal earn their premium overnight, with an offsetting intraday reversal [8]. | Entries and exits at the close (so the overnight leg is captured); overnight and intraday components are separate features. |
| Trading practice | Short-term reversal after a sharp pullback (RSI-2 style) | A 20-year Nasdaq-100 backtest: 64% winners, average winner +2.33%, average loser -3.02%, 1-4 day holds; no stops [9][10]. | The prior for A, and a reference for what a per-trade average on this kind of trade realistically looks like (well under 1% on index stocks). |

Design conclusions drawn before any code was written: (1) hold for days, not
minutes; (2) match model capacity to ~800 labels -- a shallow tree model, and
a transformer only with self-supervised pretraining; (3) treat physics and
mathematics as *feature generators and structural priors*, and let
walk-forward validation, not the elegance of the idea, decide what is used.

## 3. Design

**Timing (no look-ahead).** The decision for day *t* is made at the start of
the day's final 5-minute bar. Every feature uses only bars before that final
bar plus daily values from days before *t*. Entries and exits fill at the
final close, one bar later. All rolling statistics use days up to *t-1*.
A regression check in the blind run confirms the 2020-2023 features are
bit-identical whether or not 2024+ data is present in the file.

**Feature groups (33 causal features, `src/s12_lib.py`).**

| Group | Features |
|---|---|
| Control engineering | Kalman equilibrium; displacement z-score `z`; velocity of the equilibrium `velz`; change in displacement `dz` |
| Stochastic calculus | OU autoregression coefficient `phi`; expected 5-day reversion `ou5` |
| Mechanics analogue | signed "spring energy" of the stretch |
| Realised-volatility econometrics | today's realised volatility vs. 20-day; 5-day vs. 20-day ratio; jump share (bipower variation) |
| Information theory / fractals | permutation entropy; path efficiency; Hurst estimate |
| Rough paths | Levy area of (price, cumulative volume) and of (time, price) |
| Microstructure | overnight return, 5-day overnight and intraday sums, first-30-minute and last-hour returns, VWAP deviation, close location, up-volume share |
| Context | standardised 1/2/3/5/10/20-day returns, drawdown from 20-day high, position in 20-day range, distance from 50-day mean, volume z-score |

**Candidates.** All long-only, one position at a time, 5- or 10-day time exit,
no stop, no profit target (an average-per-trade target is not helped by
cutting winners).

- **A. Spring-release.** Enter when the displacement was below -k within the
  last 3 days, has started to shrink (`dz > 0`), and price is still below
  equilibrium. Grid: Kalman span {10, 20} x k {1.0, 1.5, 2.0} x hold {5, 10}.
- **B. Field-Fusion GBM.** Gradient-boosted trees (5 seeds, 60 trees, depth 2,
  Huber loss) predict the H-day return in excess of the training mean for
  every day; trade when the prediction is at or above the q-quantile of the
  model's own training predictions. Grid: hold {5, 10} x q {0.8, 0.9}.
- **C. Transformer probe.** 10 days of 5-minute bars (returns, range, relative
  volume) cut into 65-minute patches; a 2-layer, 48-dimension encoder
  pretrained by reconstructing 40% masked patches; frozen; ridge regression
  on the pooled embedding. Same trading rule and grid as B.
- **D. Fusion gate.** A's event, taken only when B's 5-day model predicts at
  least its training median.

## 4. Protocol, and what changed before the blind run

Folds inside 2020-2023: train 2020 -> validate 2021; train 2020-21 ->
validate 2022; train 2020-22 -> validate 2023, with labels that overlap the
validation year purged. **Selection rule:** highest t-statistic of the
per-trade *excess* return pooled over the validation years, at least 20
pooled validation trades. Excess (trade return minus the average same-length
return of all days in that year) was used so that 2020-2023's strong rise
(CNQ roughly tripled) could not pick the winner by itself.

Two rounds were run on the training years. Both are published.

- **Protocol v1** (`src/stage12_v1_protocol.py`,
  `stage12_walkforward_v1_results.json`): A entered on the first stretched
  day; B and C set their trade threshold on an inner 28% split. Findings:
  the inner-split thresholds were unstable (from -5.3 to +9.2 across folds,
  giving 1 trade in one year and 33 in another), and entering on the first
  stretched day bought falls still in progress (in 2022 the first 1-3 days
  after a stretch were negative). Under v1 the transformer scored highest,
  on the strength of a single year.
- **Protocol v2** (`src/stage12_field_fusion.py`, the one frozen): the
  "release" condition was added to A; thresholds became the quantile of the
  model's predictions on its own training rows; the meta-label candidate D
  was added; A was scored the same way as B and C (each config on its pooled
  2021-2023 trades).

Every one of these changes was made using 2020-2023 only. They are still
design choices made after looking at results, which is exactly the kind of
search that inflates validation numbers -- see Section 7.

## 5. Walk-forward results (2020-2023 only)

| Candidate | Chosen config | Pooled validation trades (2021-23) | Avg gross %/trade | Excess | t-stat of excess | Notes |
|---|---|---|---|---|---|---|
| **A. Spring-release** | span 10, k 1.5, hold 5 | 27 | +3.12% | +2.36% | **2.10** | excess positive in each year: +2.09 / +4.47 / +1.25; 78% winners |
| D. Fusion gate | A's config + B veto | 21 | +3.59% | +2.83% | 2.00 | |
| C. Transformer probe | hold 5, q 0.8 | 52 | +1.89% | +1.16% | 1.54 | rank correlation by fold -0.12 / +0.22 / +0.00: one good year |
| B. Field-Fusion GBM | hold 5, q 0.9 | 20 | +1.72% | +1.08% | 0.66 | rank correlation by fold +0.11 / +0.03 / +0.05: small but positive every year |

A was selected as the official Stage 12 model. Diagnostics run on the frozen
config before the blind test (`stage12_train_diagnostics.json`, training years
only, not used for selection):

- **Neighbourhood.** 60 nearby configs (span 8-15, k 1.25-1.75, hold 3-7
  days): all 60 had positive excess, 78% were positive in all three years,
  median excess +2.1%.
- **Permutation test.** Random entry days (same count per year) averaged
  +0.75% per trade; the rule's +3.12% was beaten by 0.7% of 20,000 random
  draws.
- **Ablation.** Stretch alone +1.06% excess; turn alone +0.24%; both together
  +2.36%.
- **Stage-10-style check** (pick on training years, score on the next year):
  fold 2 -> 2022, 11 trades, excess +0.05%; fold 3 -> 2023, 5 trades, excess
  +2.79%; fold 1 could not select (2020 has only 5 months of data).

By every in-sample measure this project uses, A looked sound.

B's most-used inputs in the final model: distance from the 50-day mean,
Kalman velocity, intraday path efficiency, OU expected reversion, the
realised-volatility ratio, Hurst, the OU coefficient and the jump share --
that is, features from control engineering, stochastic calculus,
information theory and volatility econometrics were all used by the model,
not just the plain return lags.

## 6. Blind test: 2024-2026, run once

Frozen artefact `stage12_frozen.pkl` (sha256 `6e3c7031...`), run a single time
on 723 blind days (2024-01-02 to 2026-11-18); the run is logged in
`stage12_BLIND_RUN_LOG.json` and the script refuses a second run.

| Candidate | Year | Trades | Avg gross %/trade | Win rate | Excess |
|---|---|---|---|---|---|
| A. Spring-release | 2024 | 7 | +1.71% | 57% | +1.70% |
| | 2025 | 4 | -2.27% | 25% | -2.36% |
| | 2026 | 10 | -1.77% | 30% | -2.83% |
| | **Combined** | **21** | **-0.70%** | 38.1% | -1.23% |
| B. Field-Fusion GBM | 2024 | 11 | +1.34% | 55% | +1.33% |
| | 2025 | 6 | -0.15% | 33% | -0.24% |
| | 2026 | 8 | +1.38% | 50% | +0.32% |
| | **Combined** | **25** | **+0.99%** | 48.0% | +0.63% |
| C. Transformer probe | 2024 | 12 | +0.30% | 42% | +0.29% |
| | 2025 | 18 | +0.51% | 56% | +0.42% |
| | 2026 | 21 | +0.94% | 52% | -0.11% |
| | **Combined** | **51** | **+0.64%** | 51.0% | +0.17% |
| D. Fusion gate | 2024 | 7 | +1.71% | 57% | +1.70% |
| | 2025 | 4 | -0.58% | 50% | -0.67% |
| | 2026 | 8 | +0.01% | 50% | -1.04% |
| | **Combined** | **19** | **+0.52%** | 52.6% | +0.05% |

| Candidate | 95% bootstrap interval, avg %/trade | Median trade | Best / worst trade | Avg net of 1 cent/share | Longest losing run |
|---|---|---|---|---|---|
| A | -2.84% to +1.41% | -1.20% | +8.31% / -9.94% | -0.73% | 4 |
| B | -0.88% to +2.94% | -0.40% | +13.14% / -7.35% | +0.97% | 4 |
| C | -0.50% to +1.74% | +0.10% | +8.21% / -7.30% | +0.61% | 5 |
| D | -1.43% to +2.47% | +0.46% | +8.31% / -7.71% | +0.49% | 2 |

Context for the blind period: CNQ returned -6.0% in 2024, +8.0% in 2025 and
+32.7% in 2026 to 18 November (+38.6% overall); a randomly timed 5-day long
averaged +0.35% (+0.01% / +0.09% / +1.05% by year). Daily volatility was
1.89%, down from 2.44% in training.

Checks: an independent recomputation of all 116 blind trades from the raw
5-minute file found 0 mismatches and 0 overlapping positions; re-running the
frozen artefact reproduces the stored results exactly; a full walk-forward
re-run from the published code rebuilds the frozen artefact byte for byte.

## 7. Reading this honestly

**Why the selected model failed.** The description of the blind trades
(`stage12_posthoc_description.json`, descriptive only) shows the "turn" that A
waits for was not a turn in 2025-2026: on average A's entries were down
-0.86% the next day and -1.01% after three days, recovering to +0.86% only
by day ten. In 2021-2023 the same pattern was followed by a bounce within
five days in every year. Two things are true at once:

- A was found by trying several entry conditions on the same three years
  that then "validated" it. A t-statistic of 2.1, a 0.7% permutation
  p-value and a clean neighbourhood were all computed *after* that search,
  on 27 trades. They overstated the evidence. The Stage-10-style check
  (excess +0.05% on the only fold with more than five trades) was the
  honest warning, and it was outvoted by better-looking numbers.
- The market itself differed: lower volatility, a flat-to-down 2024 and a
  fast rise in 2026 in which dips kept falling for several days before
  recovering.

**Why B is not a pass.** +0.9947% is below the bar, and even at +1.05% it
would not be a pass: the 5-day returns of its trades have a standard
deviation of about 5%, so on 25 trades the average is known only to within
roughly +/-2%. Separating a true 1% average from zero at the usual standard
needs on the order of 100 trades -- about 12 years of CNQ alone at B's rate.
Its result is carried by two trades.

**What is real.** B's day-ranking skill survived: rank correlation +0.12 on
blind days (+0.17 in 2024, +0.25 in 2025, -0.01 in 2026), against +0.03 to
+0.11 in validation. And at this holding period trading costs stop
mattering: at 1 cent per share B keeps +0.97% of its +0.99%, whereas the
same cost turns V7.1's +0.0204% negative. Summed over the blind period, B is
the first candidate in this project whose result is still positive after
costs (about +24% summed over 25 trades, against about -13% for V7.1 at the
same 1 cent) -- with the caveat above that 25 trades prove nothing yet.

**On the transformer.** Self-supervised pretraining worked mechanically
(masked-patch error fell from 0.73 to 0.48) and the probe produced a
positive but weak result (+0.64% per trade, excess +0.17%). It did not beat
the tree model on blind data, and in validation its apparent edge came from
one year. This matches the published evidence in Section 2. A larger or
pretrained model is not the lever; more independent data is.

## 8. Where Target 1 stands

| Method | Basis | Trades (2024-26) | **Avg gross %/trade** | Gap to >1%/trade |
|---|---|---|---|---|
| V7.1 (Stage 10) | blind | 1,597 | 0.0204% | ~49x short |
| Rule OR Model (Stage 10) | blind | 3,890 | 0.0178% | ~56x short |
| Percent-scaled V7.1 (Stage 11) | blind | 1,411 | 0.0205% | ~49x short |
| Donchian swing, long-only (Stage 11) | blind | 9 | -0.05% | negative |
| Donchian swing, long+short (Stage 11) | blind | 17 | -1.59% | negative |
| **Spring-release (Stage 12, selected model)** | blind | 21 | **-0.70%** | negative |
| **Field-Fusion GBM (Stage 12)** | blind | 25 | **+0.99%** | just short; not significant |
| **Transformer probe (Stage 12)** | blind | 51 | **+0.64%** | ~1.6x short; not significant |
| **Fusion gate (Stage 12)** | blind | 19 | **+0.52%** | ~1.9x short; not significant |

Stage 12 moved the best blind per-trade average from 0.02% to roughly 1%, by
changing the holding period and the kind of signal. It did not establish
that the 1% is repeatable.

## 9. Next steps (a research menu, not a plan)

1. **Do not retune anything on 2024-2026.** Those years have now been seen by
   four candidates. Any further adjustment scored on them is in-sample.
2. **Forward-test B exactly as frozen.** New CNQ bars after 2026-11-18 are
   the only clean test left on this symbol. At about 8 trades a year this is
   slow, which is the point of item 3.
3. **Bring in peer and crude-oil data** (SU, CVE, IMO, XOM, CVX, WTI). Three
   separate gains: about six times the training labels for the same model;
   a blind test on symbols the model has never seen; and enough trades
   (roughly 50 a year across six symbols) to tell a real 1% from luck within
   two years instead of twelve. This needs a data source the research
   environment can reach, or files supplied by the owner.
4. **Relative-value displacement.** Measure CNQ's stretch against its peers
   rather than against its own past. That spread is where Ornstein-Uhlenbeck
   theory actually applies; a single stock's price is close to a random walk.
5. **Selection discipline** (see `08_ML_and_Method_Development_Lessons.md`):
   freeze the design search before computing validation statistics, or hold
   back one training year that the design search never sees.
6. **For the owner:** should Target 1 carry a minimum trade count and be
   stated net of the "just being long" return? A single lucky long position
   can satisfy ">1% average per trade"; the excess column is the fairer bar.

## 10. Code and reproducibility

Run from the repository root.

| File | Purpose |
|---|---|
| `src/s12_lib.py` | data loading, 33 causal features, Kalman filter, trade simulator |
| `src/s12_transformer.py` | patch encoder, self-supervised pretraining, embeddings |
| `src/stage12_field_fusion.py` | protocol v2: `walkforward` (reads rows before 2024 only), `blind` (once), `verify` |
| `src/stage12_v1_protocol.py` | superseded first protocol, kept for the record |
| `src/stage12_train_diagnostics.py` | neighbourhood, permutation and ablation checks (training years) |
| `src/stage12_posthoc.py` | independent trade re-check and description of the blind result |
| `src/stage12_exploration/` | the five exploration scripts that led to the design (training years only) |
| `results/experiments/stage12_walkforward_results.json`, `..._v1_results.json` | validation results, both protocols |
| `results/experiments/stage12_frozen.pkl` | the frozen models (sha256 `6e3c70313afeb854fe4db9eb0fd7dff84532044ef7cc35cd046d9ddd88225817`) |
| `results/experiments/stage12_blind_results.json`, `stage12_blind_trades.csv` | blind results and all 116 blind trades |
| `results/experiments/stage12_train_diagnostics.json`, `stage12_posthoc_description.json` | diagnostics |
| `results/experiments/stage12_BLIND_RUN_LOG.json`, `stage12_pre_blind_hashes.txt` | record of the single blind run |

Requirements: Python 3 with numpy, pandas, scikit-learn and PyTorch (CPU is
enough; the whole walk-forward takes about 100 seconds).

## Sources

1. Rahimikia, Ni & Wang (2025), *Re(Visiting) Time Series Foundation Models in Finance* -- https://arxiv.org/abs/2511.18578
2. Upadhyay (2026), *Do Time-Series Foundation Models Forecast Index-Futures Returns? A Preregistered Evaluation* -- https://arxiv.org/abs/2611.12141
3. Noguer i Alonso & Franklin (2026), *Pretrained Time-Series Foundation Models for Financial Return Forecasting* -- https://arxiv.org/abs/2606.27100
4. Singh & Joubert, *Does Meta-Labeling Add to Signal Efficacy?* (Hudson & Thames) -- https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy/
5. Leung & Li (2014), *Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit* -- https://arxiv.org/abs/1411.5062
6. Chang, Lizardi & Shah (2022), *Optimizing Returns Using the Hurst Exponent and Q Learning on Momentum and Mean Reversion Strategies* -- https://arxiv.org/abs/2205.11122
7. Gyurko, Lyons, Kontkowski & Field (2014), *Extracting information from the signature of a financial data stream* -- https://arxiv.org/abs/1307.7244
8. Lou, Polk & Skouras (2019), *A Tug of War: Overnight Versus Intraday Expected Returns* -- https://personal.lse.ac.uk/polk/research/TugOfWar.pdf
9. StockCharts ChartSchool, *RSI(2)* -- https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
10. Trading Time Machine (2026), *The 2-Period RSI: A Simple System That Still Earns Its Keep* -- https://backtest.substack.com/p/the-2-period-rsi-a-simple-system
11. Souto & Moradi (2024), *Can transformers transform financial forecasting?* (abstract only) -- https://www.emerald.com/cfri/article/doi/10.1108/CFRI-01-2024-0032/1249263/Can-transformers-transform-financial-forecasting

*Research and education only, not investment advice. All results are
hypothetical backtests on one stock.*
