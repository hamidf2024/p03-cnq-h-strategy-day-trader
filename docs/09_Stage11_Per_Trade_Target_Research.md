# Stage 11: Research Toward a >1% Average Gross Return *Per Trade* (2024-2026)

*Added 2026-11-23, at the owner's direction: "develop new model and trading
method for CNQ that can reach our major goal which is more than 1 percent
gross per trade averagely for 2024 to 2026... use the same approach for
training data, 2020-2023 walk forward training and then testing on
2024-2026." This sharpens `07_Goals_and_Targets.md`'s Target 1, which had
been stated (and flagged as a working definition, pending confirmation) as
1% gross **per day**. The owner's instruction here states the metric
explicitly as **per trade**, which is a materially different, larger bar
(the per-day number is trades/day multiplied by per-trade average, so for
any realistic trade count above 1/day, per-trade is the harder target of
the two) -- see `07_Goals_and_Targets.md` for how this supersedes that
document's working definition.*

*Every number below follows the same walk-forward, out-of-sample discipline
established in Stage 10 and required by the Goals document's guardrails:
parameters are selected using only 2020-2023 training-year trades, then
2024/2025/2026 are each touched exactly once, blind, after every parameter
is already frozen. Nothing here is an in-sample or re-tuned fit.*

## 1. Deep research step: is >1%/trade structurally possible from an
   intraday, same-day setup?

Before building anything, the question was checked quantitatively against
CNQ's own 2020-2026 5-minute history (`data/raw/CNQ_5min_20200727_to_
20261118.csv`), not assumed either way.

**CNQ's own daily high-low range, 2024-2026 (the test period):**

| Year | Mean daily range (% of open) | Median | 90th pct |
|---|---|---|---|
| 2024 | 1.98% | 1.80% | 3.36% |
| 2025 | 2.25% | 1.92% | 3.36% |
| 2026 | 2.39% | 2.19% | 3.64% |

Every method this project has ever tested (V1-V7.1, Rule OR Model) is a
**same-day, end-of-day-flattened** trade. A trade that opens and closes
within one trading day cannot, on average across winners and losers, net
more than roughly half of that day's *entire* high-low range even under
a perfect-foresight entry -- and a realistic win rate/stop discipline nets
much less than that. With the average day's full range sitting at
**2.0-2.4%**, an *average, net-of-losers* return of **>1% on every trade**
from a same-day structure is not a matter of finding a better rule --
it is close to mathematically ruled out by the instrument's own volatility
at this holding period. This is the single most important finding of this
stage, and it is why Section 3 below tests a structurally different
holding period rather than another same-day rule variant.

**CNQ's rolling multi-day swing range, 2024-2026 (mean, % of the window's
starting price):**

| Window | 2024 | 2025 | 2026 |
|---|---|---|---|
| 3-day | 4.04% | 4.48% | 5.09% |
| 5-day | 5.50% | 6.07% | 6.99% |
| 10-day | 8.16% | 8.95% | 10.55% |
| 20-day | 12.04% | 12.67% | 15.46% |

A multi-day swing/trend structure, by contrast, has a plausible source of
>1%-per-trade moves -- a 10-20 day hold capturing even a modest fraction of
an 8-15% window is well above the 1% bar. Section 3 tests exactly this.

## 2. Deep research step: a well-documented systematic design for that
   holding period

Rather than inventing a new multi-day mechanism from scratch, this stage
used a long-established, precisely-specified systematic trend-following
design as the starting point: the **Donchian-channel breakout / "Turtle
Trading" system** (Richard Donchian's channel breakout, formalized by
Richard Dennis and Bill Eckhardt). Core mechanical rules, as documented
publicly ([Alchemy Markets, "Turtle Trading Guide"](https://alchemymarkets.com/education/strategies/turtle-trading-guide/)):

- **Entry:** price closes above the prior *N*-day high (long) or below the
  prior *N*-day low (short) -- classic variants use *N*=20 or *N*=55.
- **Initial stop:** 2 x ATR(20) from entry ("N" in the original terminology
  is the 20-day average true range; this project's write-up calls it
  ATR(20) throughout to avoid confusion with the channel length, also
  conventionally called N).
- **Exit:** price crosses the opposite *M*-day channel (classic *M*=10 or
  20) -- a trailing, trend-following exit, not a fixed profit target.
- **Sizing/pyramiding:** the original system risks a fixed 1% of account
  equity per unit and pyramids up to 4-5 units as a trade moves favorably.
  This project's single-unit, fixed-$100-notional-per-trade convention
  (used everywhere else on this project for comparability across methods)
  was kept instead, and pyramiding was left out of scope -- a deliberate
  simplification, stated here rather than silently assumed, consistent
  with this project's "state free parameters up front, keep the grid
  narrow" discipline.
- Reported historical stats for the original system (Curtis Faith, *Way of
  the Turtle*, as cited on the page above): win rate around 40%, profitable
  overall because winning trades run much larger than losing trades are
  allowed to -- i.e. this is a design that is *expected* to lose on a
  majority of individual trades and make it up on a minority of large
  trend captures. That expectation matters for reading Section 3's results
  honestly.

## 3. Candidate A (primary): Donchian-channel breakout swing/trend system

**What's genuinely new here, not a parameter tweak:** every prior version
(V1-V7.1, Rule OR Model) is a same-day, mean-reversion "zone bounce" that
also, per the project's own charter, is long-only. This candidate uses
daily bars (built from the 5-minute data: Open=day's first open, High/Low=
day's max/min, Close=day's last close), is held across multiple days
(trailing exit, not EOD flatten), uses a completely different signal type
(breakout, not bounce-off-a-zone), and was tested both long-only and
long+short -- the short side directly addresses the lessons document's
open, unsolved finding that a long-only design is "structurally weaker in
multi-day downtrends."

**Parameters tested (narrow 2x2 grid, stated up front):** entry channel
*N* in {20, 55}; exit channel *M* in {10, 20}. ATR window fixed at 20
(standard, not tuned); stop fixed at 2xATR (standard, not tuned); no profit
target (trailing exit only). No-look-ahead: the channel/ATR values used to
decide action on day *i* are built only from days strictly before *i*.

**Walk-forward discipline:** identical in spirit to Stage 10 --
fold1 (train 2020 -> blind-check 2021), fold2 (train 2020-2021 -> blind-
check 2022), fold3 (train 2020-2022 -> blind-check 2023), each selecting
(N, M) by best average gross %/trade **on the training years only**; final
frozen config re-selected the same way over all of 2020-2023; then each of
2024/2025/2026 (and the three combined) run exactly once, blind. One
scoped difference from Stage 10's MIN_TRADES=30 floor: swing trades are
far less frequent than 5-minute zone touches (this system produces roughly
2-9 trades per year on this single symbol), so the floor was set to 8,
stated explicitly rather than silently lowered -- and two of the three
folds still could not clear even that floor on long-only (shown as "no
candidate cleared the floor" below, not papered over).

**Results -- long + short:**

| | Train 2020-2023 (final frozen config: N=55, M=20) | Blind test 2024 | Blind 2025 | Blind 2026 | **Blind combined 2024-2026** |
|---|---|---|---|---|---|
| Trades | 11 | 6 | 6 | 5 | **17** |
| Avg gross %/trade | **+4.05%** | -0.95% | -4.64% | +1.31% | **-1.59%** |
| Win rate | 45.5% | 33.3% | 0.0% | 25.0% | 18.8% |
| Profit factor | 2.65 | 0.66 | 0.00 | 1.51 | 0.53 |

**Results -- long only:**

| | Train 2020-2023 (final frozen config: N=55, M=20) | Blind 2024 | Blind 2025 | Blind 2026 | **Blind combined 2024-2026** |
|---|---|---|---|---|---|
| Trades | 8 | 2 | 4 | 3 | **9** |
| Avg gross %/trade | **+7.06%** | +1.38% | -4.11% | +4.41% | **-0.05%** |
| Win rate | 62.5% | 50.0% | 0.0% | 33.3% | 22.2% |
| Profit factor | 4.74 | 1.57 | 0.00 | 3.14 | 0.98 |

**Reading this honestly:** the training-fold averages (+3.1% to +7.9%/
trade across all three folds, both variants) looked spectacular -- clearing
the 1% target by a wide margin -- but every one of the three walk-forward
validation folds (the genuinely blind year inside 2020-2023) came back
**negative** (-1.24% to -3.17%/trade), and the final frozen config's blind
test on 2024-2026 stayed **roughly breakeven to negative** (-0.05% for
long-only, -1.59% for long+short), not a validated improvement. This is
the textbook signature this project's own lessons document warns about:
a small sample (8-26 training trades per candidate, 9-17 in blind test)
can look excellent in-sample purely by chance, and this one did not
survive out-of-sample checking. Looking at the actual blind-test trades
(2024-2026, long-only) makes the mechanism visible directly: 2 large
winners (+7.55%, +19.43%, both multi-month trend captures) and 7 stop-outs
in the -1.9% to -4.8% range -- exactly the shape a trend-following system
is *designed* to produce (frequent small losses, funded by occasional large
wins), but this window didn't produce enough big wins, on one symbol, to
make the arithmetic work out positive. That is consistent with how these
systems are known to behave (Section 2's cited win rate of ~40% on the
original multi-market Turtle system) -- they are built to be run across
many markets and many years so the large-winner tail shows up often enough;
run on one symbol over 2-3 years, 9-17 trades is too small a sample for
that tail to reliably appear, which is itself evidence for the basket/
multi-symbol direction already queued in `07_Goals_and_Targets.md`'s
candidate list, not a reason to abandon the mechanism.

**Conclusion for Candidate A:** does not validate >1%/trade, or even a
reliably positive edge, on CNQ alone over 2024-2026 -- but it is the first
method tested all project that is even *structurally capable* of the
multi-percent single-trade moves the 1%/trade target requires (the +19.43%
and +7.55% trades prove the mechanism can capture real multi-day trend
moves on this instrument), which no same-day method can do by construction
(Section 1). The honest limiting factor is trade-count/sample-size on a
single symbol, not the mechanism itself.

## 4. Candidate B (secondary, cheaper check): percent-of-price-scaled V7.1

**Motivation (data-grounded, from Section 1's own price-history check):**
CNQ's own average close rose from **$9.86** (2020) to **$45.62** (2026) in
this dataset -- a 4.6x increase -- while V7/V7.1's stop/target have stayed
fixed in **cents** (0.10/$0.20 normal, 0.15/$0.30 wide day) since they were
tuned on the original 32-day window. A $0.20 target was a ~2% move at 2020
prices and is now under a 0.5% move at 2026 prices -- a real, mechanical
reason "Avg gross %/trade" could be understating the strategy's own
designed edge in later years. This candidate asks a narrow, specific
question: does simply re-expressing V7.1's existing, already-validated
entry/exit rule with a **percent-of-price** stop/target (instead of fixed
cents) change the picture, with nothing else changed?

**Design (scoped, stated explicitly):** band/cutoff frozen at V7.1's
existing Stage-10-selected values (band=0.02, cutoff=12:55) to isolate the
effect of percent-scaling alone. Stop/target percentages are derived from
the original cent values at the 2020 reference price ($9.86): base stop
1.01%, base target 2.03% (and the wide-day equivalents). A small grid
(target width x1 or x2 or x4 the base percentage) was walk-forward tested.
One stated simplification: rather than a true per-trade percent (which
would require forking the ~300-line backtester's exit-management loop),
each YEAR's dollar offset was fixed from that **prior** year's average
close (2020 bootstraps off its own first 20 days) -- i.e. "what V7.1 would
look like if its cent offsets were re-set once a year to track the stock's
then-current price level," not a live per-trade percent. No look-ahead: a
year's offset never uses that year's own (future, from the trade's point
of view) average price.

**Results:**

| | Train 2020-2023 (chosen: 1x base stop, 1x base target) | Blind 2024 | Blind 2025 | Blind 2026 | **Blind combined 2024-2026** |
|---|---|---|---|---|---|
| Trades | 1,816 | 503 | 536 | 372 | **1,411** |
| Avg gross %/trade | 0.048% | 0.008% | 0.027% | 0.028% | **0.0205%** |
| Win rate | 65.6% | 70.3% | 69.4% | 69.1% | 69.7% |
| Profit factor | 1.40 | 1.09 | 1.35 | 1.37 | 1.25 |
| Avg at 1 cent/share cost | -0.008% | -0.021% | -0.006% | +0.006% | -0.008% |

**Conclusion for Candidate B:** essentially a null result -- the walk-
forward grid search chose the narrowest (1x) stop/target on every fold and
the final config, and the blind combined average (**0.0205%/trade**) is
statistically indistinguishable from V7.1's existing Stage-10 result
(**0.0204%/trade**, from `07_Goals_and_Targets.md`). Percent-scaling the
offsets does not meaningfully change the per-trade edge in practice,
because the actual captured win/loss sizes (driven by the weak-candle
early-exit rule, not the nominal stop/target distance) were already
tracking price level reasonably well through other channels (the zone-
touch band itself, `band=0.02`, is also a fixed-dollar tolerance, not
percent-scaled -- left untouched here to isolate one variable at a time,
and flagged as a further variant worth testing if this one had shown
promise, which it did not).

## 5. Where this leaves Target 1 (per-trade framing)

| Method | Basis | Trades (2024-2026) | **Avg gross %/trade** | Gap to >1%/trade |
|---|---|---|---|---|
| V7.1 (Stage 10, walk-forward) | blind | 1,597 | 0.0204% | ~49x short |
| Rule OR Model (Stage 10, walk-forward) | blind | 3,890 | 0.0178% | ~56x short |
| Percent-scaled V7.1 (Stage 11, new) | blind | 1,411 | 0.0205% | ~49x short |
| Donchian swing, long-only (Stage 11, new) | blind | 9 | -0.05% | negative |
| Donchian swing, long+short (Stage 11, new) | blind | 17 | -1.59% | negative |

**Read plainly:** no method this project has built and honestly walk-
forward validated -- old or new -- averages anywhere close to a reliably
positive >1%-per-trade return on blind 2024-2026 data. The best positive,
high-volume result (percent-scaled V7.1) sits at roughly **1/49th** of the
target. The one method that is structurally *capable* of multi-percent
single trades (the Donchian swing breakout) does not yet have enough
trade volume on one symbol to validate that capability as a reliable,
positive average -- its blind-test result is a small, negative-to-breakeven
sample, not a disproof of the mechanism.

## 6. Concrete next steps (a research menu, not a plan -- same framing
   as `07_Goals_and_Targets.md`'s Section on candidate directions)

1. **Basket/multi-symbol for the swing system specifically.** Section 3's
   core limitation is trade count (9-17 trades over 3 years on one
   symbol). Running the identical Donchian breakout logic across several
   liquid, correlated symbols (SU, CVE, IMO, XOM, CVX -- already queued in
   `07_Goals_and_Targets.md`) would multiply trade count without changing
   the per-symbol mechanism, giving the walk-forward selection and the
   blind test enough samples to actually distinguish "this works" from
   "this got unlucky" -- which the current single-symbol result cannot do
   either way.
2. **A hybrid: proven high-win-rate zone-bounce entries, swing-style exit
   management.** V7.1's entry confirmation (72.9% win rate, full history)
   is this project's single most-validated signal. Pairing that entry with
   Candidate A's multi-day trailing-stop exit (instead of V7.1's own
   same-day EOD-flatten) is a genuinely untested combination -- not the
   same thing as the four already-rejected "let winners run" variants
   (Section 5 of `08_ML_and_Method_Development_Lessons.md`), all of which
   were same-day exit-timing tweaks on the existing mean-reversion
   mechanism, not a change to the holding period itself.
3. **Wider ATR multiple / time-stop for Candidate A.** This stage tested
   only the classic 2xATR stop and channel-only exit. A 3xATR stop (fewer
   whipsaw stop-outs, Section 3's trade log) or an explicit maximum holding
   period are both narrow, single-knob variants worth testing before
   concluding the mechanism itself is unviable on CNQ.
4. **Re-confirm the Target 1 metric with the owner.** This document used
   "per trade" exactly as instructed. `07_Goals_and_Targets.md`'s original
   working definition (now superseded for Target 1's headline number, kept
   there for the per-DAY framing specifically) still has open questions
   about compounding and multi-symbol account-level returns that apply
   here too, now that a materially harder bar is in play.

## 7. Code and reproducibility

- `src/stage11_swing_breakout.py` -- Candidate A, full implementation
  (daily-bar construction, ATR/channel calculation with no-look-ahead
  shifting, single-pass multi-day simulation, walk-forward fold selection,
  $100-notional stats). Raw results: `results/experiments/
  stage11_swing_results.json`.
- `src/stage11_pct_scaled.py` -- Candidate B, implementation (thin wrapper
  around `bt7_unified_backtester_v1_to_v71.run_version`, see the module's
  own docstring for the stated per-year-not-per-trade simplification).
  Raw results: `results/experiments/stage11_pct_scaled_results.json`.
- Both reuse `bt7_unified_backtester_v1_to_v71.py`'s existing, already-
  validated V7.1 logic and the project's established $100-notional /
  Gross % convention, per the process lesson in Section 6 of
  `08_ML_and_Method_Development_Lessons.md` ("persist the actual code, not
  just its prose description").
