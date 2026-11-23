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
here rather than silently left out.*

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
