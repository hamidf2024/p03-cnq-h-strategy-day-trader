# Lessons for Future ML Model & Trading Method Development

*Added 2026-11-23, at the owner's direction ("create lessons learned document
to capture all lessons during model and method development and results which
could be used for developing new ML models and trading methods"). This is a
different document from `06_Lessons_Learned.docx`: that file is the
stage-by-stage research log (one dated entry per rule-change test, in the
order it happened). This file instead pulls the generalizable, reusable
lessons out of that log and out of Stages 8-10 specifically, organized by
topic rather than by date, so a future ML model or new trading method can be
built without re-learning the same things the hard way. Every claim below
traces back to a dated entry in `06_Lessons_Learned.docx` or to Stage 9/10's
own results (see citations in each section) -- nothing here is new analysis,
it is a reorganization of what this project already found.*

*Note on scope: `06_Lessons_Learned.docx` does not yet have a Stage 10 entry
(it currently ends at Stage 9, 2026-11-18). The walk-forward findings below
draw on Stage 10's actual results (published on project-03.html and in
`src/stage10_walk_forward_training.py`), but a formal dated research-log entry
for Stage 10 still needs to be added to `06_Lessons_Learned.docx` -- flagged
here rather than silently left out.* *(Resolved 2026-11-23: dated Stage 10,
Stage 11 and Stage 12 entries are now in `06_Lessons_Learned.docx`. From
Stage 12 on, each stage's lessons are filed directly into the topic section
they belong to below, marked with the stage number, and indexed in a short
per-stage section at the end.)*

## 1. Data lessons

- **Vendor differences matter when thresholds are sub-cent.** This project's
  zone-touch tolerance is as tight as 1.2 cents (`band=0.012`). Cross-checking
  Alpaca's IEX feed against the original Yahoo consolidated-tape file over
  their overlap window showed close but not tick-for-tick agreement (median
  diff ~0.01%, max ~0.46%) -- close enough for the rule-based backtester,
  but NOT close enough for a candidate-level ML pipeline built on the
  IEX-sourced history to reproduce the same window's numbers that the
  original Yahoo-sourced file gave. **Lesson for future ML work:** before
  trusting any model trained on a new data source, re-run the exact bar-for-
  bar regression check (below) on that specific source, even if the
  underlying rule engine already passed it on a different source. A model
  trained on slightly different prices will learn slightly different
  candidates and thresholds, and the mismatch compounds instead of averaging
  out. (Stage 9, `06_Lessons_Learned.docx`.)
- **Stock splits and corporate actions need explicit handling, and need to be
  checked against a reproducibility gate, not assumed.** CNQ's 2024-06-11
  2-for-1 split was split-adjusted when the 6.3-year history was acquired;
  the fix was verified by confirming the already-published 32-day window
  still reproduced exactly after splicing in the adjusted long history.
  **Lesson:** any new data source (a new symbol for the basket test, a
  different vendor, intraday vs. daily-adjusted feeds) needs the same
  "reproduces a known-good result exactly" gate before anything built on top
  of it is trusted.
- **More history changes the honest picture a lot, and always in the
  direction of regression to the mean.** V7.1's headline numbers on the
  original 32-day tuning window (72.9% win rate, PF 3.81, net/trade 0.036)
  dropped to 61.3% / 1.31 / 0.0078 across the full 6.3-year, 3,605-trade
  history -- still genuinely positive in every one of 7 calendar years, but
  roughly 4-5x weaker per trade than the narrow window suggested. **Lesson
  for new methods (rule-based or ML):** never report or compare models using
  a sample under a few hundred trades without flagging that explicitly; a
  model that looks excellent on 75 trades should be assumed to regress
  toward something much more modest once tested on years, not weeks, of data.

- **(Stage 12) One symbol's own bars leave out its main driver, and cap how
  much any model can learn.** Stage 12 had only CNQ's 5-minute bars; peer
  stocks and crude oil could not be reached from the research environment.
  Every candidate therefore had ~800 daily labels to learn from and ~8-17
  blind trades a year to be judged on. **Lesson:** for a multi-day method,
  treat peer and driver data (here SU, CVE, IMO, XOM, CVX, WTI) as a
  prerequisite, not an extension -- it multiplies training labels, supplies
  symbols the model has never seen for a clean test, and is the only
  practical way to reach a trade count that can confirm or reject an edge.

- **(Stage 13 preparation) Read the feed and the licence before choosing a
  data source, not after.** The data-source review
  (`11_Peer_and_Oil_Data_Sources.md`) found three things that had been missed
  when the CNQ history was first acquired: the vendor's free plan allows the
  consolidated feed for historical requests (the CNQ file used the IEX feed,
  about 2.5% of market volume, which is a likely contributor to the vendor-
  sensitivity noted above); the vendor states its data may not be
  redistributed, while this repository is public; and a widely used free
  mirror of the official oil-price series forbids machine-learning use in
  its terms, where the official source is public domain. **Lesson:** for
  every new data source record, before the first download, which feed it
  is, what share of the market it covers, and what its terms say about
  model training and publication -- and prefer the primary publisher over a
  mirror.
- **(Stage 13) Peer data was the missing ingredient for the profit goal.** One
  model trained on six oil stocks at once (six times the labels) is the first
  in the project to clear 1% per trade on unseen years, in each year
  (+1.41%, 39 trades). The CNQ-only version of the same idea reached 0.99% on
  25 trades with one losing year. **Lesson:** before adding model capacity,
  add independent rows; related instruments are the cheapest source.

## 2. Labeling and feature engineering lessons (for ML specifically)

- **Label candidates by simulating the existing rule engine's own management,
  not by a naive "would this have been profitable" heuristic.** Stage 8's ML
  candidate set labels every zone touch in the entry window (not just the
  ones the hand rule would take) by running V7.1's *exact* stop/target/
  ratchet/exit logic forward from that bar. This keeps the label consistent
  with how a trade would actually have been managed, instead of a simplified
  proxy (e.g. "price up N bars later") that the execution logic wouldn't
  actually have captured.
- **A model is only as trustworthy as its ability to reproduce the rule
  engine's own numbers when restricted to the rule engine's own candidates.**
  Before trusting any ML result, Stage 8 restricted the candidate set to
  exactly the touches V7.1's hand rule would confirm and replayed them
  sequentially; this reproduced V7.1's official numbers bar-for-bar (0
  mismatches) before any ML number was reported. This check caught two real
  implementation bugs (a break-statement misread in the zone-exit loop, and
  conflating the entry band with a separate swing-confirmation band) that
  would otherwise have silently corrupted every downstream ML result.
  **This is the single most important process lesson in this document: build
  the validation-against-known-good-output gate before trusting any new
  numeric result, every time, not just once.**
- **Candidate volume is small relative to what high-capacity models need.**
  28 training days produced 475 labeled candidates (Stage 8); even the full
  6.3-year history produces on the order of a few thousand per year (Stage
  10's 2020 training fold: 1,956 ML candidates from V7.1's logic). This is
  why a transformer was explicitly ruled out (this project's own Project 9
  and Project 13 pages independently found transformers need far more data
  than this) and a shallow, heavily regularized gradient-boosted model
  (`GradientBoostingClassifier(n_estimators=60, max_depth=2, learning_rate=
  0.05, subsample=0.8)`) was used instead. **Lesson:** match model capacity to
  the realistic candidate count for one symbol at 5-minute resolution; a
  bigger model is not a free upgrade here, and the basket/multi-symbol
  expansion (queued, not yet done) is the more promising way to get more
  training data, not a bigger model on the same single-symbol data.
- **A model that matches win rate without matching trade selection is a
  different, not better, signal.** The Stage 8 ML-alone model matched V7.1's
  win rate almost exactly (73.1% vs. 72.9%) but only 5 of its 36 highest-
  confidence picks overlapped with the 95 rule-confirmed candidates in the
  same test window. **Lesson:** always check candidate overlap with the
  existing rule's picks, not just aggregate metrics -- a model can look
  competitive in isolation while actually having learned something entirely
  different and weaker.

- **(Stage 12) Label every day, not only the event days.** The Field-Fusion
  model predicted the 5-day excess return for all ~800 training days rather
  than for the ~40 days a rule would have traded. Its fold-by-fold rank
  correlation was small but positive every year (+0.11 / +0.03 / +0.05) and
  it held on blind data (+0.12), while the far better-looking event rule
  reversed. **Lesson:** when events are scarce, train on the dense version of
  the question and trade only the top of the ranking; and prefer a small
  signal with the same sign in every fold over a large one in one fold.
- **(Stage 12) A transformer can be given enough data by self-supervised
  pretraining on the bars -- and still not beat a shallow tree model.** A
  PatchTST-style encoder pretrained by masked-patch reconstruction on
  62,000 five-minute bars, frozen, with a ridge probe, produced +0.64% per
  blind trade (excess +0.17%) against the tree model's +0.99% (excess
  +0.63%); its validation edge came from a single year. This agrees with
  the 2025-2026 literature on time-series foundation models for returns
  (zero-shot models at or below tree baselines). **Lesson:** this refines
  the earlier "transformer ruled out" note: the obstacle is not that a
  transformer cannot be trained here, it is that model capacity is not the
  binding constraint -- independent data is.
- **(Stage 12) Ideas from other fields earn their place as features, not as
  trading rules.** Kalman-filter displacement and velocity, Ornstein-
  Uhlenbeck expected reversion, realised-volatility ratios, jump share,
  Hurst and path-efficiency measures were all among the tree model's most-
  used inputs. The one candidate that turned a physics picture directly
  into a rule (the "spring-release" entry) was the one that failed blind.
  **Lesson:** use physics, control and information-theory constructs to
  describe the state of the market causally, and let a regularised model
  and walk-forward validation decide how much weight each deserves.
- **(Stage 13) Set entry thresholds on the model's own recent forecasts.** A
  trailing rank over the last 120 out-of-sample forecasts gave 37 validation
  and 39 test trades; Stage 12's fixed training quantile gave 25 where 72
  were expected. **Lesson:** in-sample forecasts are more spread out than live
  ones; a causal trailing rank keeps trade frequency stable.
- **(Stage 13) The model with the best rank correlation was not the best to
  trade.** The transformer had the highest out-of-fold rank correlation
  (0.076 against 0.059 for gradient boosting), yet the ensemble containing it
  traded worse than gradient boosting alone, on validation and on test.
  **Lesson:** judge a forecaster on the trades its top forecasts produce, not
  on its average correlation.

## 3. Overfitting-prevention lessons (the ones that generalize beyond this project)

- **A fix that's traced back to one single trade is not a fix -- it's
  curve-fitting, and should be rejected regardless of how good it looks.**
  Two concrete, explicitly rejected examples from Stage 5/7: widening the
  wide-day stop past 0.15 looked like a step-function improvement, but
  traced back to exactly one historical trade's exact stop-out level; fine-
  tuning the entry cutoff to the exact minute looked like a local peak, but
  traced back to one added winning trade offsetting one added losing trade
  five minutes later. **Lesson:** every proposed improvement should be
  decomposed by which specific trades it changes before being accepted --
  if the effect lives in one or two trades, reject it even if the headline
  metric improved.
- **A narrow, deliberately small grid beats a search over per-trade special
  cases.** Stage 10's walk-forward parameter selection used only 2 broad
  knobs (`band`, `entry_cutoff`) across a 3x3 grid (9 combinations) --
  explicitly contrasted with the REJECTED_* curve-fit presets already on
  file from earlier stages. **Lesson for any future optimization, ML or
  rule-based:** the number of free parameters searched should be small and
  stated up front, not grown opportunistically as new ideas come up mid-
  cycle -- the more combinations tried, the more some combination will look
  good purely by chance, especially on a few hundred trades.
- **Select on out-of-sample fold performance, never on in-sample fit, and
  enforce a minimum trade floor.** Stage 10's expanding-window folds (train
  2020 → validate 2021; train 2020-2021 → validate 2022; train 2020-2022 →
  validate 2023) picked parameters by net-per-trade on the *validation* year,
  never the training year, with a floor of 30 trades per candidate so no
  combination could win by getting lucky on a handful of trades. All 9
  validation folds across V7/V7.1/Rule-OR-Model stayed win-rate >58% and
  profit-factor >1.2 with no collapse from fold to fold -- the textbook
  negative signature of overfitting (great in-sample, falls apart out of
  sample) did not show up, which is itself evidence (not proof) the
  selection discipline worked.
- **The test years must be touched exactly once, after every parameter is
  already frozen -- never used to pick or re-pick anything.** Stage 10's
  2024/2025/2026 blind test years were run through the frozen final config a
  single time each, with no retuning between years. **Lesson:** the instant a
  "test" year gets used to adjust a parameter, even once, it has become a
  training year in every way that matters for honesty about the result.
- **An ML probability threshold must be chosen on a split *inside* the
  training window, never on the fold's own validation/test data.** Stage
  10's Rule-OR-Model picks its GBM threshold on an inner time-split of the
  last ~28% of each fold's training days, before ever looking at that fold's
  validation year. This is the same principle as the point above, one level
  deeper (it applies to a hyperparameter of the model, not just to the
  model's own predictions).
- **Walk-forward-selected parameters can differ meaningfully from hand-tuned
  ones, and that's useful information, not just a curiosity.** Stage 10's
  walk-forward selection converged on `band=0.02, cutoff=12:55` for both
  V7 and V7.1 in the final frozen config and 2 of 3 folds -- wider and
  earlier than the hand-picked `band=0.012, cutoff=13:55` from the original
  32-day tuning window. **Lesson:** the parameters that look best on a short,
  hand-picked window are not necessarily the parameters that generalize
  best; whenever a new method is walk-forward tested, compare its selected
  parameters against any hand-tuned version and treat a large divergence as
  a signal about what the hand-tuning window was and wasn't representative
  of, not just noise.
- **Exploit any no-cross-day-state property of the simulator for speed, but
  verify the assumption first.** `run_version()` resets zones, position, and
  attempt counters at the start of every trading day, and the only thing
  computed outside the per-day loop (`prior_hlc`) is built once from the
  full `days` list before any subsetting. This means a trade list for any
  date range equals the union of running each day individually, so one
  trade list per (config, year) can be cached and composed by concatenation
  instead of re-simulating overlapping ranges for every grid candidate --
  this is what made Stage 10's 72-job grid search and three models' walk-
  forward folds complete in minutes rather than hours. **Lesson for a new
  method:** check for this property explicitly before relying on it (a
  method with real cross-day state, e.g. a multi-day position or a trend
  filter using a rolling window that spans day boundaries, would break this
  optimization silently and produce wrong cached results).

- **(Stage 12) The design search is part of the fit.** The spring-release
  rule's final form (enter only after the stretch has started to shrink)
  was chosen by trying several entry conditions on 2021-2023 -- the same
  years then used to "validate" it. On those years it showed a t-statistic
  of 2.1, a permutation p-value of 0.007 and positive results in all 60
  neighbouring parameter settings. On blind 2024-2026 it lost 0.70% per
  trade. **Lesson:** statistics computed after a search over rule *forms*
  are in-sample no matter how they are labelled. Either freeze the form
  before looking at any validation number, or hold back one training year
  that the design search never touches and confirm on it before the blind
  run. Count the variants tried and say so next to the result.
- **(Stage 12) A clean parameter neighbourhood is not independent evidence.**
  All 60 neighbours of the frozen rule were positive in training, which
  looked like robustness. They were 60 slightly different views of the same
  ~27 trades in the same three years. **Lesson:** neighbourhood checks
  detect knife-edge parameters; they say nothing about whether the effect
  exists outside the sample. Do not count them as confirmation.
- **(Stage 12) When two validation views disagree, believe the stricter
  one.** Scored the Stage-10 way (pick on the training years, score on the
  next year) the same rule family showed +0.05% excess on its only fold with
  more than five trades. The pooled view showed +2.36%. The pooled view was
  used; the strict view was right. **Lesson:** a result has to survive the
  harshest reasonable validation available, not the most flattering.
- **(Stage 12) Check a threshold by the trade count it produces in each
  fold, not only by the average it produces.** The first protocol set ML
  trade thresholds on a small inner split; they ranged from -5.3 to +9.2
  across folds and produced 1 trade in one year and 33 in another. The
  average looked fine. **Lesson:** an unstable trade count is a broken
  threshold; anchor thresholds to something stable (here, a quantile of the
  model's own predictions on its training rows) and inspect per-fold counts
  before reading any performance number.
- **(Stage 13) A gate passed in a rising market proves little.** On 2021-2023
  buying CNQ on any day for 5 days averaged +1.04%, and 53% of months were
  above 1%. Model J passed "level 1 in every validation year" with zero excess
  over entering on any day. **Lesson:** every validation gate needs a
  no-skill line built with the same exit rule; report the excess beside the
  raw level.
- **(Stage 13) Repeating until a goal is met changes what the result means.**
  Six models were run on 2024-2026 in this stage, the last two designed after
  earlier results were known. **Lesson:** log every look in a file the code
  enforces, state the count beside the result, and treat a level reached this
  way as a candidate for forward testing, not as a finding.
- **(Stage 13) Passing a gate exactly at its threshold is not passing.**
  Model N cleared level 1 on all four goals in every training year with 8, 8
  and 8 qualifying months against a requirement of 8, 8 and 7, then scored 6,
  8 and 5 on the test years. **Lesson:** require a margin on any counted
  goal (for example one month to spare in every year) before spending a test
  run, and treat a setting that passes with none as a fail.
- **(Stage 13) Write the gate before the search, and let "nothing passed" be
  a result.** After N the gate was tightened in code first (one month of
  margin on each month goal in every training year, and the same rule on the
  five peer stocks), then 112 settings were run with the test years removed.
  None passed, so no run on 2024-2026 was made. A search that ends without a
  test run is the gate working, not a wasted stage.
- **(Stage 13) Check whether a goal can be met by counting instead of by
  trading.** GM adds up the percentages of a month's trades, so opening two
  $1,000 trades on the same day doubles the month's total without changing
  the bet. When a goal can be reached by splitting or repeating a position,
  say so and ask the owner how the goal should count before reporting it as
  reached.
- **(Stage 13) Size the stop against the stock's ordinary swing.** CNQ moves
  about 2% on an ordinary day. On the training years a stop of 1% to 3% was
  hit in more than half of the monthly trades and the win rate fell below
  50%; every step wider improved the win rate and the month goals, up to the
  15% limit. A stop inside the noise is a cost, not protection. Test the
  whole range on training data before choosing one, and remember the range
  was priced in rising years.
- **(Stage 13) Hold the gate hardest when the answer looks known.** Model O
  was model M with two buys at different times, and M's test result was
  already public, so a good test result for O was likely. On the training
  years O reached level 1 exactly, with no spare month in 2021, and the gate
  stopped it. A gate that is waived when the outcome is expected to be good
  is not a gate; the decision to run anyway belongs to the owner and is
  recorded as such.
- **(Stage 13) Settle how a goal counts before designing to it.** GM adds up
  trades, so the owner was asked whether trades opened together count
  separately. The answer (same time: one trade; different times: separate)
  went into the charter and the scoring code before any model used it.

## 4. Evaluation and metrics lessons

- **Trading costs are not optional and change which method wins.** The
  backtester reported no commissions/spread/slippage until Stage 7.1. At a
  realistic 1-2 cent/share round-trip cost, only V7 and V7.1 stay profitable
  at all among the 8 rule versions, and even they go net-negative in most
  individual years once tested honestly (Stage 9's year-by-year cost table:
  V7.1 net-negative in 6 of 7 years at 1 cent/share). Stage 10 confirmed this
  again under genuine walk-forward training, not just hand-tuned parameters:
  all three methods (V7, V7.1, Rule OR Model) go net negative in 2024 and
  2025 at 1 cent/share, and are only marginally positive in 2026. **Lesson:
  any new model or method must be judged net of a stated realistic cost
  before being called viable, not just on gross edge** -- gross edge
  surviving out-of-sample is necessary but has not yet been sufficient for
  any method this project has tested.
- **A consistent per-trade normalization makes methods with very different
  trade counts comparable.** The `$100/trade` convention (100 / entry_price
  shares, i.e. return on a fixed $100 notional per trade) and its percentage
  form (`Gross %`) are used throughout so that a method generating 5 trades/
  day can be compared on equal footing with one generating 2/day, without
  the raw $/share totals being misread as directly comparable (e.g. Stage
  8's "Rule OR model" posted a larger total $/share than "Rule AND model
  agrees" mostly because it had 83 trades vs. 17, not because its per-trade
  quality was better -- the per-trade and Gross % columns make that visible
  immediately where a raw total wouldn't).
- **A metric that only measures "quality per trade" can hide the real
  question, and vice versa.** Profit factor and win rate measure trade
  quality; net $/share (or Gross % summed per day) measures total output.
  Stage 8's "Rule AND model agrees" variant had the best win rate (83.3%) and
  profit factor (17.6) of anything tried in the whole project, on only 17
  trades -- not enough volume to beat V7.1 on total net profit, the owner's
  stated #1 priority, but flagged as worth revisiting once more data gives
  it room to generate more trades. **Lesson:** report both dimensions
  together, every time, and don't let a strong result on one dimension stand
  in for the other.

- **(Stage 12) For any multi-day long method, report the return in excess of
  simply being long.** A randomly timed 5-day long in CNQ averaged +0.92% in
  2020-2023 and +0.35% in 2024-2026. A long swing rule inherits that for
  free, so its raw average per trade overstates its skill. **Lesson:** next
  to every per-trade average for a held position, report the same-length
  random-entry return and the difference, and select on the difference.
- **(Stage 12) Work out the sample size the claim needs before running the
  test.** Five-day CNQ trades have a standard deviation of about 5%. Telling
  a true 1% average from zero needs on the order of 100 trades; the blind
  period supplied 19-51 per candidate. The Field-Fusion model's +0.99% has
  a 95% interval of -0.88% to +2.94%. **Lesson:** if the available blind
  data cannot deliver the required number of trades, say so before the run
  and plan how to get it (more symbols, more time), instead of discovering
  afterwards that neither success nor failure can be established.
- **(Stage 12) An average-per-trade target is driven by a few trades; show
  what is left without them.** Two of the Field-Fusion model's 25 blind
  trades (+13.1%, +10.3%) account for almost all of its +0.99% average; the
  other 23 average +0.06%, and the median trade is -0.40%. **Lesson:** always
  report the median and the average excluding the top one or two trades
  beside any per-trade average. This is the multi-day version of the
  project's existing "traced to one trade" rule.
- **(Stage 12) Costs stop mattering once the per-trade move is large.** At 1
  cent per share the Field-Fusion model keeps +0.97% of +0.99% per trade,
  where the same cost turns V7.1's +0.0204% negative. **Lesson:** the cost
  problem found in Stages 9-10 belongs to very small per-trade edges, not to
  CNQ; holding period is the most direct lever on it.
- **(Goal scoring) A win rate that drops break-even trades can hide a third
  of the trades.** Scored on 2024-2026, V7.1 percent-scaled wins 70.2% of
  decided trades but 46.3% of all trades, because 34% of its trades end
  within half a cent of entry. Under the first number it reaches WR2; under
  the second it reaches nothing. **Lesson:** print the scratch count and the
  wins-of-all-trades figure beside any win rate, and settle which one a goal
  means before scoring against it.
- **(Goal scoring) "Above 1% for the month" has two readings that rank the
  methods in opposite order.** The steadiness goal was first scored as the
  month's summed gross return above 1%; the owner meant the month's average
  per trade above 1%. Under the sum, Rule OR Model led with 8 of 12 months
  in every year, on 3,890 trades of +0.018% each. Under the average, no
  same-day method has a single qualifying month in 35 (best month 0.13% per
  trade) and the multi-day models lead with 3 to 5 months a year. **Lesson:**
  a summed-return measure rewards trade count, an average rewards per-trade
  edge; say which one a goal uses, in the goal's own sentence.
- **(Goal scoring) A steady monthly average needs edge and frequency
  together.** The multi-day models clear 1% per trade in some months but
  trade in only 16 to 29 of 35 months, and a qualifying month is often one
  trade. **Lesson:** report months-with-trades beside months-above-target,
  and treat a one-trade month as weak evidence.
- **(Goal scoring) A composite ranking moves with every definition under
  it.** The same fixed rule gave two different top fives before and after
  the steadiness correction. **Lesson:** fix the ranking rule before
  computing it (done here), and publish the leader of each goal, the
  after-cost flag and the trade count beside it so the ranking is never read
  alone.
- **(Stage 13) Goals that count winners reward small wins and large losses.**
  A +4% target with no stop reached WR3 and S1 with 31 winners and four
  losers of up to 17%. Win rate and months-above-target say nothing about
  the size of the losses. **Lesson:** beside any goal that counts winners,
  report the worst trade, the average loser, the capital at work when trades
  overlap, and the result of the same exit entered on any day.
- **(Stage 13) Work out what a goal requires before building for it.** A
  short calculation on training data showed S1 needs 75 to 80% directional
  accuracy with time-based exits, far beyond any model here. That redirected
  the work from forecasting to exit design after one round instead of many.
  **Lesson:** turn each goal into a required accuracy or edge first.
- **(Stage 13) Count months by entry and say so.** S places a trade in its
  entry month, so a trade that takes two months to reach its target still
  makes its entry month count. **Lesson:** state the attribution rule next to
  any per-period count.
- **(Stage 13) Set the risk limit before the performance goals are chased.**
  The owner's 5% worst-trade rule was added after model J had reached all
  three levels with losses of 17%. Under the rule J is out, and the same
  design with a 5% stop averages zero. **Lesson:** a goal set needs its
  loss limit from the start; otherwise the search finds the designs that the
  missing limit allows.
- **(Stage 13) Show what a limit costs on training data, not on the test
  years.** The effect of stops at 5, 8, 10 and 15% was tabulated on 2021-2023
  only, so the owner can choose a level without another look at 2024-2026.

## 5. Strategy-domain lessons (useful context for any new method on this instrument/timeframe)

- **A zone can play two roles (entry trigger and exit checkpoint), and a fix
  aimed at one role can silently break the other.** The Opening-Range zone
  was found not to be something the owner actually enters on (0 of 14 real
  annotated trades touched an OR-zone level as an entry), but removing it
  entirely made results worse because it also removed its value as an exit
  checkpoint for unrelated trades. The fix that actually worked was demoting
  it to exit-only, not removing it. **Lesson:** before changing or removing
  any rule component in a new method, check whether it's doing more than one
  job.
- **The single most common real-trading mistake was entering on the first
  touch of a new high/low before a zone was actually confirmed by a second
  test** -- this recurs across essentially every discretionary audit note in
  Part 1 of `06_Lessons_Learned.docx`, and is why first-touch vs. confirmed-
  zone tagging is treated as a first-class concept in the rule engine, not
  an afterthought.
- **A root cause traced to a specific, generalizable mechanism (not a single
  trade) is the bar for a real fix.** V7→V7.1's fix (reject OPEN-zone wick
  bounces that don't reclaim the day's open) came from splitting trades by
  confirmation type, zone kind, and entry price vs. the day's open, and
  found a 44% vs. 80% win-rate split that held across the full tested range
  -- not a single-trade artifact. It improved every headline metric at once,
  which is the standard this project holds every accepted change to.
- **"Let winners run" ideas have been tried four separate ways and rejected
  every time on this instrument/timeframe.** A price-proximity gate, a
  cooldown change, a 2-candle confirmation requirement, and a ratchet-gated
  version were all tested as ways to capture more of the nominal 2:1 stop/
  target ratio (realized average win and average loss are close to each
  other in practice, not 2:1, because the primary exit rule closes winners
  early). All four reduced net P&L. **Lesson for a new method:** this is a
  settled negative finding specific to this zone-bounce, mean-reversion-style
  setup -- don't re-spend research cycles re-testing "let winners run"
  variants without a genuinely new mechanism, but also don't assume the
  finding transfers to a structurally different method (e.g. a trend-
  following or breakout method) without re-testing it there.
- **A long-only design is structurally weaker in multi-week downtrends, and
  the mechanical fixes tried so far didn't help.** A trailing trend filter
  and a downtrend stop multiplier both made results worse; a downtrend zone
  filter showed a small improvement but on only 7 trades -- too fragile to
  adopt. This remains an open, unsolved problem and the most likely reason
  a short-side mirror (queued, not yet built) could add real, non-redundant
  value rather than just more of the same trades.

- **(Stage 12) How long a pullback takes to recover is not a stable
  property.** In 2021-2023, buying after a stretched pullback had started to
  turn was followed by a bounce within five days in every year. In 2025-2026
  the same entries were down 0.9% the next day and 1.0% after three days, and
  were positive only by day ten. **Lesson:** a fixed holding period tuned on
  one regime is a hidden parameter; the volatility level (1.89% a day blind
  against 2.44% in training) and the speed of the surrounding trend both
  changed the recovery time.
- **(Stage 13) First-passage exits turn a market's swing into a high hit
  rate.** For CNQ, +2% within 20 days was reached in 82 to 96% of trades and
  +4% within 60 days in 87 to 89%, in both the training and the test years.
  The cost is the tail: the trades that miss lose 6 to 17%. **Lesson:** a
  target exit is a way to shape results, not a source of edge; its average
  equals the market's drift over the holding time plus whatever the entry
  adds.
- **(Stage 13) Relative value against peers and oil was real but small.**
  The spring rule's excess was +1.3% per trade on validation and +0.4% on
  test, with half its trades short. **Lesson:** useful as a feature (it is
  inside model E), weak as a stand-alone rule.

## 6. Process lessons (how this project avoided repeating its own mistakes)

- **Persist the actual code, not just its prose description and outputs.**
  An early backtester lived only in a prior session's temporary storage and
  was lost when that session ended; Version 5 had to be rebuilt from the
  written rule spec, and the rebuild wasn't an exact match (the "second
  pullback" zone-confirmation test had never been given a precise numeric
  definition, so the rebuilt engine's reading of it differed slightly).
  **This is why every stage from Stage 9 onward ships both a results write-up
  and the actual script that produced it** (e.g. `stage10_walk_forward_
  training.py`), committed to the repository, not described only in prose.
- **Regression-check every new build against a known-good output before
  trusting anything built on top of it.** Every version change has been
  re-checked against an established known-good result before new numbers
  were reported (V6 against its own known output; Stage 8's ML pipeline
  against V7.1's official numbers; Stage 9's full-history data against the
  original 32-day window; Stage 10's smoke test against its own fold-1
  numbers). This single habit has caught real bugs every time it's been
  applied (see Section 2) and should be the first step of any new model or
  method, not an afterthought once results look plausible.
- **Log rejected experiments with the same rigor as accepted ones.** The
  REJECTED_* presets, the four rejected "let winners run" variants, the two
  rejected downtrend fixes, and the ML-alone/AND-filter variants that didn't
  beat V7.1 on net profit are all kept on file with their reasoning, not
  deleted. **Lesson:** a negative result that's well isolated (e.g. "traced
  to one trade, rejected" or "made every metric worse") is exactly as
  valuable as a positive one for stopping a future research cycle from
  re-testing the same dead end.

- **(Stage 12) Make "the blind test is run once" a property of the code, not
  a promise.** Stage 12 hashed the frozen models, logged the single blind
  run, made the script refuse a second run, kept a separate `verify` mode
  that only re-runs the identical artefact, and exercised the blind code
  path on training data first (a dry run) so a coding slip could not force
  a second look at the blind years. **Lesson:** build these guards before
  the run; they cost minutes and remove the temptation and the ambiguity.
- **(Stage 12) Publish the superseded protocol and the exploration scripts.**
  The first protocol, its validation results and the five exploration
  scripts that led to the final design are in the repository. **Lesson:**
  the path to a design is part of the evidence about it -- in this case it
  is what explains why the selected model's validation numbers were too
  good.
- **(Goal scoring) Save the per-trade list of every blind run.** Stages 10
  and 11 saved only totals, so scoring the new goals meant re-running six
  frozen configurations and first proving they reproduced the published
  trade counts and averages. They did, exactly, but only because the code
  and configurations were frozen. **Lesson:** a new question about an old
  result needs the trades, not the summary; write the trade list out at the
  time, and keep a regression check that fails loudly if a re-run differs.
  It paid off the same day: the steadiness correction was re-scored from the
  saved lists in seconds, with no re-run.
- **(Goal scoring) Restate a new goal with one worked example before scoring
  it.** The steadiness goal was scored, documented and published on a
  misreading, then redone. One line back to the owner ("a month counts when
  X; for example model M in March would count because ...") would have
  caught it. **Lesson:** when a goal's wording allows two formulas, show the
  formula and an example and get a yes before building on it.
- **(Stage 13) Publish and report each model as it lands.** Each model was
  frozen, run once, scored, put on the website and reported before the next
  was designed. **Lesson:** it keeps the record of what was known when each
  design was made, which is what makes the count of looks honest.

## 7. What this means for Stage 11 / new ML models, concretely

Tying the above back to `07_Goals_and_Targets.md`'s Target 1 (1% gross
return per day, currently 10-22x out of reach across all validated methods):

1. **Trade frequency, not just per-trade edge, is a lever worth researching
   directly.** The Rule OR Model's advantage on daily gross came from firing
   roughly 2.4x as often as V7/V7.1, not from a better per-trade edge (its
   per-trade average is in fact the lowest of the three methods tested in
   Stage 10). Any new ML model aimed at closing the Target 1 gap should be
   evaluated on *trades/day contributed*, not only on win rate / profit
   factor, and the labeling approach in Section 2 (label every zone touch,
   not just hand-rule-confirmed ones) is already set up to support this.
2. **Scale candidate volume before scaling model complexity.** Section 2's
   finding (candidate counts are small relative to what high-capacity models
   need) means the basket/multi-symbol expansion (Stage 7.3, queued) is a
   higher-value next step for ML development than a bigger model on the same
   single-symbol data.
3. **Any new model must go through the full gate before being trusted:**
   reproduce a known-good baseline bar-for-bar first (Section 2), select
   parameters only on out-of-sample fold performance with a minimum trade
   floor (Section 3), freeze before touching test years, test each blind
   year exactly once, and report net-of-cost, not just gross (Section 4).
   None of this is optional just because the model is new or the stakes
   (the 1%/day target) are higher than before -- if anything, the larger the
   target, the larger the temptation to curve-fit toward it, and the more
   this discipline matters.

## 8. Stage 11 additions (per-trade target research, 2026-11-23)

*The owner sharpened Target 1 to >1% gross **per trade** (see
`07_Goals_and_Targets.md`'s 2026-11-23 update) -- a materially harder bar
than per-day. Stage 11 (`09_Stage11_Per_Trade_Target_Research.md`) is the
research cycle run against it. These lessons generalize beyond that
specific target.*

- **Check the instrument's own volatility against the target BEFORE
  building anything, not after.** Stage 11 computed CNQ's actual daily
  high-low range (2024-2026: ~2.0-2.4% of open, on average) before writing
  a single line of model code, and that one number by itself ruled out
  every same-day trade structure for a >1%-net-of-losers-per-trade target
  -- a same-day trade cannot average more than roughly half the day's own
  total range, even with perfect entries. **Lesson: for any numeric
  per-trade or per-period target, compute the instrument's own realized
  range at the intended holding period FIRST** -- it tells you immediately
  whether the target is a modeling problem (find a better rule within a
  feasible structure) or a structural one (the holding period itself must
  change), and saves real effort that would otherwise go into tuning a
  structure that cannot reach the number by construction.
- **A multi-day/swing structure opens up per-trade magnitudes a same-day
  structure cannot reach, but trades far too infrequently to validate
  reliably on one symbol.** Stage 11's Donchian-channel breakout swing
  system produced individual blind-test trades of +7.55% and +19.43% --
  both impossible for any EOD-flattened method -- but only 9-17 total
  blind trades across 3 full years, net to a roughly breakeven-to-negative
  average. **Lesson: when a new method's edge shows up only in rare, large
  trades (a trend-following profile, not a high-frequency one), a 2-3 year
  single-symbol blind test is very likely too small a sample to tell
  "doesn't work" apart from "hasn't had enough chances yet" -- treat this
  pattern as a signal to scale sample size (multi-symbol/basket) before
  concluding the mechanism itself failed, not as a disproof on its own.**
- **"Let winners run" being rejected 4 times for the existing mean-reversion
  setup (Section 5 above) did not transfer to a genuinely different holding
  structure, exactly as flagged it might not.** Stage 11's swing system IS
  a "let winners run" design in spirit (a trailing channel exit, no fixed
  target) and, unlike the 4 earlier same-day variants, it did produce real
  outsized winners in blind testing. It still didn't net positive overall
  in this particular 3-year window -- but for a different reason (sample
  size, per the point above), not the same reason the 4 same-day variants
  failed. **Lesson: when a prior negative finding is retested on a
  structurally different method, as this project's own lessons explicitly
  recommend, a different outcome for a different reason is a useful,
  distinct result -- don't collapse it into "still doesn't work" without
  checking WHY it didn't work this time.**
- **Percent-of-price scaling a fixed-dollar rule is worth checking
  explicitly when the price level has moved a lot, but check it before
  assuming it explains a gap.** CNQ's average price rose 4.6x (2020 to
  2026) across this project's data while V7/V7.1's stop/target stayed
  fixed in cents -- a plausible, concrete reason "Avg gross %/trade" could
  be smaller than the strategy's designed edge in later years. Stage 11
  tested this directly and found an **essentially null result** (0.0205%
  vs. the original 0.0204%/trade) -- the walk-forward grid search picked
  the narrowest offset on every fold, meaning this specific mechanism
  (band/zone-touch tolerance staying fixed-dollar, and the weak-candle
  early-exit rule dominating actual captured win/loss size over the
  nominal stop/target distance) already tracks price level well enough
  through other paths. **Lesson: a plausible mechanical hypothesis for why
  a number looks small is still worth testing on its own, even when (maybe
  especially when) it later turns out not to be the explanation -- a
  quick, narrowly-scoped null result is cheap and closes off a specific,
  recurring question (reviewers/the owner will keep asking "did you
  account for the price change?" otherwise) rather than being wasted
  effort.**

## 9. Stage 12 additions (field-fusion swing research, 2026-11-23)

*Stage 12 (`10_Stage12_Field_Fusion_Research.md`) built four multi-day
candidates on 2020-2023 -- a physics-based rule, a gradient-boosted model
over features from several fields, a self-supervised transformer, and a
meta-labelled combination -- and ran each once on 2024-2026. Target 1 was
not met: the model chosen by validation lost 0.70% per trade; the best
candidate averaged +0.99% on 25 trades, not statistically distinguishable
from zero. The lessons are filed in the topic sections above, each marked
"(Stage 12)":*

- Section 1 (data): single-symbol data is the ceiling; peer and driver data
  are a prerequisite for multi-day work.
- Section 2 (ML): label every day; a pretrained transformer did not beat a
  shallow tree model; other fields' ideas work as features, not as rules.
- Section 3 (overfitting): the design search is part of the fit; a clean
  neighbourhood is not independent evidence; believe the stricter
  validation view; check thresholds by per-fold trade count.
- Section 4 (evaluation): report excess over being long; compute the
  required sample size first; show the average without the top trades;
  costs fade at multi-day holds.
- Section 5 (strategy): pullback recovery time is regime-dependent.
- Section 6 (process): enforce the single blind run in code; publish the
  superseded protocol and exploration scripts.

*Added after Stage 12, in preparation for Stage 13: one data lesson in
Section 1 on checking a source's feed and licence before first use
(`11_Peer_and_Oil_Data_Sources.md`).*

## 10. Goal-ladder scoring additions (2026-11-23)

*The owner set three goals with three levels each (gross % per trade: 1 / 2 /
more than 3; win rate: 50 / 65 / more than 75; months per year in which the
average trade is above 1%: 8 / 10 / 12 of 12) and asked for $1,000 per trade
as the dollar basis. All 16 methods were scored on 2024-2026
(`src/goals_scorecard.py`, `07_Goals_and_Targets.md`). No method reaches
level 1 on all three. The steadiness goal was first scored on the month's
summed return and corrected the same day to the month's average per trade.
The lessons are filed above, each marked "(Goal scoring)":*

- Section 4 (evaluation): show wins of all trades beside the win rate; a sum
  and an average rank methods in opposite order; a steady monthly average
  needs edge and frequency together; never read a composite ranking alone.
- Section 6 (process): save per-trade lists from every blind run and gate
  re-runs on reproducing published numbers; restate a new goal with a worked
  example before scoring it.


## 11. Stage 13 additions (peer-and-oil models, 2026-11-23)

*Stage 13 (`12_Stage13_Peer_Fusion_Research.md`) built six models with the
peer and oil data. E, a pooled gradient-boosted model, reached G1 and WR1.
J, one trade a month with a +4% target and no stop, reached level 1 on all
three goals on 2024-2026, with cautions about its loss shape and the number
of test runs. Lessons are filed above, each marked "(Stage 13)":*

- Section 1 (data): peer data supplied the independent rows the profit goal
  needed.
- Section 2 (ML): trailing-rank thresholds; rank correlation is not trade
  performance.
- Section 3 (overfitting): a gate passed in a rising market proves little;
  repeated runs change what a result means.
- Section 4 (evaluation): goals that count winners reward negative skew;
  compute what a goal requires first; state how months are attributed; set
  the risk limit before chasing the goals and price it on training data.
- Section 5 (strategy): first-passage exits shape results and carry a tail;
  relative value is a feature, not a rule.
- Section 6 (process): publish and report each model as it lands.
- Section 3 (overfitting), added after model N: a pass at the threshold is
  not a pass; write the gate before the search and accept an empty result;
  check whether a goal can be met by counting trades rather than by trading.
