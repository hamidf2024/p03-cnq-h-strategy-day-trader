# Goals & Targets

*Added 2026-11-23, at the owner's direction ("define target and goals for this
project; first target and goal is developing a model/method which can have 1%
gross per day"). This document sits alongside `00_Project_Charter.docx` (the
project's original objective and priority order) and `01_Phases_of_Development.docx`
(the stage-by-stage roadmap) rather than replacing them: the charter's priority
order is kept below as a guardrail, and this file adds the first concrete,
numeric performance target the project is now aimed at.*

## Update 2026-11-23: three goal ladders (current goals)

The owner replaced the single target with three goals, each with three levels,
and asked for dollar figures on $1,000 per trade instead of $100. They are
recorded in `00_Project_Charter.docx` ("Performance Goals") and scored by
`src/goals_scorecard.py`.

| Goal | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| **G**: average gross % per trade | G1: 1% | G2: 2% | G3: more than 3% |
| **WR**: win rate | WR1: 50% | WR2: 65% | WR3: more than 75% |
| **S**: months per year in which the average gross % per trade is above 1% | S1: 8 of 12 | S2: 10 of 12 | S3: 12 of 12 |
| **GM**: months per year whose trades add up to 5% or more (added 2026-11-23) | GM1: 8 of 12 | GM2: 10 of 12 | GM3: 12 of 12 |

**Definitions used for scoring.** All on the blind years 2024-01-02 to
2026-11-18, with the configuration each method froze in its own stage.

- G: profit per share / entry price x 100, before costs, averaged over trades.
  On $1,000 per trade, G1 = $10, G2 = $20, G3 = more than $30 per trade.
- WR: wins / (wins + losses). A trade within half a cent per share of zero is
  a scratch and is left out (the project's convention since V1). The share of
  all trades that made money is given in brackets.
- S: a month counts when the average gross % per trade of the trades opened
  in it is above 1%. A month with no trade does not count. A level must hold
  in every year; 2026 has 11 months and is judged on the same fraction.
  *Corrected 2026-11-23:* the first scoring counted months whose summed gross
  % was above 1%. The owner confirmed the test is the average per trade
  within the month, and everything below uses that.
- GM (fourth goal, added by the owner 2026-11-23): a month counts when the
  gross % of the trades opened in it add up to 5% or more, $50 or more at
  $1,000 per trade. The owner confirmed the reading with an example: +4%,
  +4% and -2% make +6% and the month counts. Counted per year like S.
- After costs: 1 cent per share for the round trip, about $0.28 on a $1,000
  trade.

### Risk rule set by the owner, 2026-11-23: worst trade within 5% (strict) and 15% (wide)

The owner first set a 5% limit on the loss of any single trade, then asked for
5% and 15% to be considered together. Every model must carry a stop. A
model's levels count, and it is ranked, only inside the 15% limit; each model
is also marked as inside or outside the 5% limit. A model keeps a limit if it
has a stop at that level or tighter by design, or if its worst test trade was
within it. A gap through the stop can still make one loss somewhat larger;
the worst trade is reported. Reason: WR and S count how often trades win, not
how much the losers lose, and model J reached all three levels with no stop
and losses of up to 17%.

### Scorecard, blind 2024-2026, $1,000 per trade (four goals, two loss limits)

Months are listed as 2024 / 2025 / 2026 (2026 has 11 months).

| Rank | Model | Trades | G: avg gross %/trade | WR | S: months averaging above 1% per trade | GM: months totalling 5% or more | Levels | Worst trade and limit kept | $ per trade after 1 cent |
|---|---|---|---|---|---|---|---|---|---|
| 1 | M. One-a-month, 15% stop | 35 | +1.85% | 88.6% | 10 / 12 / 9 | 0 / 1 / 0 | G1 WR3 S1 GM0 | -15.7%, within 15% | +$18.18 |
| 2 | N. Two-a-month campaign | 68 | +0.74% | 70.6% | 6 / 8 / 5 | 6 / 8 / 5 | G0 WR2 S0 GM0 | -15.7%, within 15% | +$7.10 |
| 3 | E. Peer-Fusion GBM | 39 | +1.41% | 60.5% | 6 / 4 / 4 | 3 / 2 / 2 | G1 WR1 S0 GM0 | -7.1%, within 15% | +$13.77 |
| 4 | L. Peer-Fusion GBM, 5% stop | 39 | +1.05% | 60.5% | 6 / 4 / 3 | 3 / 3 / 1 | G1 WR1 S0 GM0 | -5.0%, within 5% | +$10.17 |
| 5 | K. One-a-month, 5% stop | 35 | +0.02% | 71.4% | 8 / 10 / 7 | 0 / 0 / 0 | G0 WR2 S0 GM0 | -5.4%, within 5% | -$0.12 |
| 6 | H. Peer-Fusion, target and stop | 38 | +0.85% | 55.3% | 6 / 3 / 2 | 3 / 3 / 1 | G0 WR1 S0 GM0 | -5.0%, within 5% | +$8.22 |
| 7 | C. Transformer probe | 51 | +0.64% | 51.0% | 3 / 3 / 5 | 1 / 2 / 4 | G0 WR1 S0 GM0 | -7.3%, within 15% | +$6.09 |
| 8 | G. Fusion ensemble | 38 | +0.81% | 56.8% | 1 / 3 / 3 | 1 / 3 / 2 | G0 WR1 S0 GM0 | -7.5%, within 15% | +$7.85 |
| 9 | F. Peer-and-oil spring | 56 | +0.43% | 50.9% | 3 / 6 / 4 | 1 / 3 / 3 | G0 WR1 S0 GM0 | -8.0%, within 15% | +$4.04 |
| 10 | B. Field-Fusion GBM | 25 | +0.99% | 48.0% | 3 / 2 / 2 | 1 / 0 / 1 | G0 WR0 S0 GM0 | -7.3%, within 15% | +$9.65 |
| 11 | D. Fusion gate | 19 | +0.52% | 55.6% | 4 / 2 / 2 | 1 / 0 / 1 | G0 WR1 S0 GM0 | -7.7%, within 15% | +$4.88 |
| 12 | V7.1 percent-scaled | 1,411 | +0.02% | 70.2% | 0 / 0 / 0 | 0 / 1 / 0 | G0 WR2 S0 GM0 | -2.0%, within 5% | -$0.08 |
| 13 | Rule OR Model | 3,890 | +0.02% | 59.9% | 0 / 0 / 0 | 0 / 1 / 4 | G0 WR1 S0 GM0 | -0.6%, within 5% | -$0.10 |
| 14 | V7 | 1,834 | +0.02% | 59.9% | 0 / 0 / 0 | 0 / 0 / 0 | G0 WR1 S0 GM0 | -0.6%, within 5% | -$0.10 |
| 15 | V7.1 | 1,597 | +0.02% | 59.4% | 0 / 0 / 0 | 0 / 0 / 0 | G0 WR1 S0 GM0 | -0.6%, within 5% | -$0.08 |
| 16 | A. Spring-release | 21 | -0.70% | 40.0% | 4 / 1 / 2 | 1 / 0 / 1 | G0 WR0 S0 GM0 | -9.9%, within 15% | -$7.32 |
| 17 | V5 | 2,284 | +0.01% | 55.0% | 0 / 0 / 0 | 0 / 0 / 1 | G0 WR1 S0 GM0 | -0.6%, within 5% | -$0.18 |
| 18 | V6 | 1,794 | +0.02% | 56.2% | 0 / 0 / 0 | 0 / 0 / 0 | G0 WR1 S0 GM0 | -0.6%, within 5% | -$0.13 |
| 19 | V4 | 2,188 | +0.01% | 49.3% | 0 / 0 / 0 | 0 / 1 / 1 | G0 WR0 S0 GM0 | -0.6%, within 5% | -$0.16 |
| 20 | V3 | 2,741 | +0.01% | 49.3% | 0 / 0 / 0 | 0 / 1 / 1 | G0 WR0 S0 GM0 | -0.6%, within 5% | -$0.16 |
| 21 | V2 | 2,124 | +0.01% | 49.1% | 0 / 0 / 0 | 0 / 0 / 0 | G0 WR0 S0 GM0 | -0.6%, within 5% | -$0.18 |
| 22 | V1 | 1,654 | +0.02% | 38.0% | 0 / 0 / 0 | 0 / 1 / 0 | G0 WR0 S0 GM0 | -0.6%, within 5% | -$0.13 |
| 23 | Donchian swing, long+short | 17 | -1.59% | 18.8% | 2 / 0 / 1 | 0 / 0 / 1 | G0 WR0 S0 GM0 | -7.2%, within 15% | -$16.16 |
| not ranked | J. One-a-month campaign | 35 | +2.24% | 88.6% | 10 / 12 / 9 | 0 / 1 / 0 | G2 WR3 S1 GM0 | -17.3%, OVER 15% | +$22.14 |
| not ranked | I. First-passage campaign | 78 | +0.59% | 84.6% | 6 / 7 / 9 | 3 / 1 / 4 | G0 WR3 S0 GM0 | -17.3%, OVER 15% | +$5.65 |
| not ranked | Donchian swing, long-only | 9 | -0.05% | 22.2% | 1 / 0 / 1 | 1 / 0 / 1 | G0 WR0 S0 GM0 | -5.0%, within 5% | -$0.75 |

**Attempt at level 1 on all four goals (model N, 2026-11-23).** Two trades a
month (one in each half), +6% target, 15% stop, 60-day limit; chosen on
2021-2023 with the test years removed from the data, where it reached level 1
on all four goals in every year (G +2.60%, WR 79.7%, S 8 / 8 / 8, GM 8 / 8 / 7
of 10). On 2024-2026, one run: 68 trades, **+0.74% per trade, 70.6% win rate,
S 6 / 8 / 5, GM 6 / 8 / 5**; 12 trades stopped at 15%; year totals +14.9%,
+55.4%, -20.0%; up to five trades open at once. It reaches WR2 only. Level 1
on all four goals is not reached. This was the twentieth walk-forward model
run on 2024-2026.

**The fourth goal, GM.** No model reaches GM1. The closest inside the loss
limits is E. Peer-Fusion GBM with 3 / 2 / 2 months of 5% or more.
Model M is far from it by design: one trade a month sold at +4% makes a
month's total of about 4% (it reached 5% once in 35 months). GM needs several winning trades in the same month,
which pulls against the one-trade-a-month design that reaches S. The ranking
now averages progress on all four goals: M. One-a-month, 15% stop, E. Peer-Fusion GBM, L. Peer-Fusion GBM, 5% stop, K. One-a-month, 5% stop, H. Peer-Fusion, target and stop.

**Where the project stands.**

- **Inside the 15% limit, model M reaches level 1 on all three goals:**
  one trade a month, +4% target, 15% stop, 60-day limit. 35 trades, +1.85%
  per trade (G1), 88.6% win rate (WR3), 10 / 12 / 9-of-11 qualifying months
  (S1). 31 trades hit the target; four were stopped at about 15%. Its 95%
  range is -0.4% to +3.5%; on the training years it lost money in 2022; up to
  three trades are open at once; it was the ninth Stage 13 model run on the
  test years. It needs confirming on new data.
- **Inside the 5% limit no model reaches level 1 on all three.** The closest
  are L (model E with a 5% stop: +1.05%, 60.5%; G1 and WR1) and K (one trade
  a month with a 5% stop: 71.4% win rate, 8 / 10 / 7-of-11 months, but +0.02%
  per trade).
- Model J (no stop) is outside both limits and is not ranked.

**What the stop level costs, on the training years only** (one trade a
month, +4% target, 2021-2023): stop 5%: G +0.57%, WR 62.5%, S 7 / 7 / 6.
8%: +0.62%, 71.9%, 7 / 8 / 8. 10%: +0.93%, 78.1%, 8 / 9 / 8. 15%: +1.44%,
84.4%, 9 / 9 / 9. None: +2.80%, 87.5%, 9 / 10 / 9.

**Top five** (models inside the 15% limit; rule otherwise unchanged): M. One-a-month, 15% stop, E. Peer-Fusion GBM, K. One-a-month, 5% stop, L. Peer-Fusion GBM, 5% stop, H. Peer-Fusion, target and stop.

**Other cautions.** Every same-day model loses money after the 1 cent cost.
Nineteen walk-forward models have now been run on 2024-2026.

V1 to V6 use rules set by hand on Jul-Aug 2026, which lies inside the blind
period, so their scores are flattering. The earlier targets below are kept
as history.

## Update 2026-11-23: Target 1 sharpened to per-TRADE (supersedes the
   per-day working definition's headline bar)

Later the same day, the owner's instruction became explicit: "develop new
model and trading method for CNQ that can reach our major goal which is
more than 1 percent gross per trade averagely for 2024 to 2026... use the
same approach for training data, 2020-2023 walk forward training and then
testing on 2024-2026." This resolves one of the open questions below in
the harder direction: **per trade**, not per day. For any realistic trade
count above 1/day (every method tested so far runs 2-5/day), per-trade is
the materially bigger bar of the two (per-day = trades/day x per-trade), so
this is now Target 1's headline number; the per-day table immediately below
is kept for context and because it's still a live, useful secondary view,
not because it's still the primary bar.

Stage 11 (`09_Stage11_Per_Trade_Target_Research.md`) is the research cycle
run directly against this per-trade bar. Short version: **no method tested
so far, old or new, averages anywhere close to >1% gross per trade on
honest 2024-2026 blind data** -- the best positive, high-volume result
(a percent-of-price-scaled variant of V7.1, tested in Stage 11) sits at
0.0205%/trade, about 1/49th of target. Stage 11 also tested a genuinely
new trade *structure* (a multi-day ATR/Donchian-channel swing-trend system,
since a same-day structure is close to ruled out by CNQ's own ~2%/day
average range -- see that document's Section 1 for the quantitative check)
-- it proved capable of individual trades in the +7% to +19% range (which
no same-day method can produce by construction) but did not yet validate a
reliably *positive* average on one symbol over only 9-17 blind trades.
Full methodology, results tables, and next steps: see
`09_Stage11_Per_Trade_Target_Research.md`.

## Update 2026-11-23 (Stage 12): four multi-day candidates tested blind;
   Target 1 still not met, best blind result +0.99% per trade

The owner asked for a new, innovative model drawing on machine learning
(including transformers) and on mathematics, physics and engineering, under
the same discipline (walk-forward on 2020-2023, blind on 2024-2026). Stage 12
(`10_Stage12_Field_Fusion_Research.md`) built and froze four multi-day,
long-only candidates and ran each once on 2024-2026:

| Method | Basis | Trades (2024-2026) | **Avg gross %/trade** | Excess over a random 5-day long | Gap to >1%/trade |
|---|---|---|---|---|---|
| Spring-release rule (the model selected by validation) | blind | 21 | **-0.70%** | -1.23% | negative |
| Field-Fusion GBM | blind | 25 | **+0.99%** | +0.63% | just short; 95% interval -0.88% to +2.94% |
| Transformer probe | blind | 51 | **+0.64%** | +0.17% | ~1.6x short |
| Fusion gate | blind | 19 | **+0.52%** | +0.05% | ~1.9x short |

**Target 1 status: not met.** The selected model failed outright. The best
candidate is about 49 times V7.1's per-trade average and is the first result
in this project that stays positive after a 1 cent/share cost (+0.97% per
trade), but it is below 1%, rests on 25 trades, and two of those trades
supply nearly all of the average. It is a lead to confirm on new data, not a
result. The 2024-2026 years have now been used by these candidates and must
not be used to retune them.

Open question added for the owner: should Target 1 carry a minimum number of
trades, and be stated in excess of simply holding CNQ for the same number of
days? A randomly timed 5-day long averaged +0.35% over 2024-2026, so part of
any long multi-day result is the stock's own rise rather than the method.

## Guardrails carried over from the charter (unchanged)

Per `00_Project_Charter.docx` (amended 2026-10-28), the owner's priority order
remains: **(1)** maximum net profit **after trading costs**, counted only if
it holds on data the rules weren't tuned on; **(2)** a higher win rate;
**(3)** a reasonable number of trades (roughly 1-3/day). Everything below is
additive to this order, not a replacement for it. In particular: a method
that hits a high daily-return number by firing large numbers of low-quality
trades, at the cost of win rate, profit factor, or net-of-cost profit, does
**not** satisfy the project's goals even if it clears the number in Target 1.
Every number reported against Target 1 must be produced under the same
walk-forward, out-of-sample discipline established in Stage 10 (train/validate
on past years only, freeze, test blind exactly once) -- never from an in-sample
or re-tuned fit.

## Target 1 -- average gross return of 1% per day

**Statement:** develop a model/method for CNQ 5-minute trading whose average
**gross** return per trading day reaches **1.00%**, validated out-of-sample.

**Working definition (stated explicitly since the owner's instruction didn't
spell out the exact measure -- please confirm or correct):** "gross % per day"
is computed the same way "Gross %" already is everywhere else on this project's
results pages -- a $100 notional position sized at each trade's own entry price
(100 / entry_price shares), before any commission/spread/slippage -- summed
across every trade opened on a given calendar day, then averaged across all
trading days in the test period. It is **not** compounded intraday (each
trade's $100 is independent, not the running account balance), and it does
**not** assume leverage or margin. If the owner instead means a compounded
account-level daily return, or a return computed across multiple concurrently
held symbols, that changes the research direction materially (see "Open
questions" below) and should be confirmed before Stage 11 work is scored
against this target.

### Where the project stands today (the gap)

All figures below are out-of-sample / walk-forward validated (Stage 9's full
7-year hand-tuned run, and Stage 10's genuine walk-forward-trained blind test
on 2024-2026), never in-sample fits:

| Method | Basis | Trades | Trading days | Trades/day | Avg gross %/trade | **Avg gross %/day** | Gap to 1%/day |
|---|---|---|---|---|---|---|---|
| V7.1 (hand-tuned, Stage 9, full 2020-2026 history) | 7-yr walk-forward-unchanged | 3,605 | 1,584 | 2.28 | 0.0317% | **0.072%** | ~14x short |
| V7 (Stage 10, walk-forward-trained, blind 2024-2026) | blind test, frozen config | 1,834 | 723 | 2.54 | 0.0189% | **0.048%** | ~21x short |
| V7.1 (Stage 10, walk-forward-trained, blind 2024-2026) | blind test, frozen config | 1,597 | 723 | 2.21 | 0.0204% | **0.045%** | ~22x short |
| Rule OR Model (Stage 10, walk-forward-trained, blind 2024-2026) | blind test, frozen config | 3,890 | 723 | 5.38 | 0.0178% | **0.096%** | ~10x short |

**Reading this honestly:** every method validated so far, on real out-of-sample
data, averages somewhere between 0.045% and 0.096% gross per trading day --
roughly a tenth to a fifth of the 1%/day target. The closest of the four,
Rule OR Model, gets there mainly through trading *more often* (5.4 trades/day
vs. ~2.2-2.5 for the rule-only methods) rather than a materially better
per-trade edge (its 0.0178% average per trade is in fact the lowest of the
four) -- an early, genuine signal that trade frequency is at least as
promising a lever as per-trade edge for closing this gap, not just a
consolation point for a method that otherwise ranked behind V7/V7.1 on net
profit.

### Back-of-envelope: what closing the gap would take

Holding entry quality roughly where it is now (~0.02-0.03% gross/trade, the
range these methods have actually shown out of sample), reaching 1%/day on
CNQ alone would need on the order of **35-55 trades per day** -- roughly
10-20x today's 2-5/day -- which is not realistic for a single-symbol,
long-only, zone-bounce setup on 5-minute bars without a fundamentally
different source of trades. Holding trade count roughly where it is now
(~2-5/day), reaching 1%/day would need a per-trade edge of **roughly
0.2-0.5%**, which is 7-25x any per-trade edge this project has validated out
of sample so far (including the narrow, since-revised-down 32-day V7.1
tuning window's 0.0785%/trade). In practice, closing a gap this size almost
certainly needs **both** levers moved substantially, plus likely a widening
of scope beyond "more signals on the same symbol" (see candidates below).

### Candidate directions for Stage 11 (not yet tested -- a research menu, not a plan)

Each of these would need its own walk-forward-validated, no-look-ahead,
anti-overfitting test (same discipline as Stage 10) before being trusted,
exactly like every version before it:

1. **Trade frequency.** Rule OR Model's edge over V7/V7.1 on this specific
   metric came from firing more often. Worth directly researching what drives
   that (lower confirmation bar, the ML model catching candidates the hand
   rule misses) and whether frequency can be pushed further without giving up
   the win rate / profit factor guardrail.
2. **Concurrency.** Every version so far is one-trade-at-a-time. Allowing
   multiple concurrent positions (e.g. different zones touched the same day)
   within a stated risk budget would multiply daily gross directly, without
   needing a better per-trade edge -- but needs its own risk-manager design
   and is a "materially bigger departure" in the same sense the project's own
   code comments already flag for stop/target changes.
3. **Per-trade edge.** Wider or asymmetric stop/target ratios, a stronger
   confirmation bar, or added features (the zone-strength score and
   relative-volume filter already queued in Stage 7.4/7.5 of
   `01_Phases_of_Development.docx`) could lift the ~0.02-0.03% average.
4. **Additional setups beyond zone-bounce.** A fundamentally different signal
   type (not just a parameter tweak on the existing one) adds trade
   opportunities that don't trade off against the existing rule's quality.
5. **Basket / multi-symbol.** Stage 7.3 (queued, not yet done) -- running the
   validated logic across several liquid, correlated symbols (SU, CVE, IMO,
   XOM, CVX) multiplies daily opportunity count across an account even if no
   single symbol's frequency changes. This interacts directly with the
   "Open questions" below on what "per day" means at the account level.
6. **Short side.** Stage 7.6 (queued, not yet done) -- mirrors the rule at
   resistance zones for down days, which is pure upside to trade count on
   days the long-only version currently sits out.

### Open questions for the owner (please confirm before Stage 11 is scored against this target)

- Is "1% gross per day" meant as defined above (sum of independent $100
  per-trade returns, no compounding, single symbol), or as a compounded
  account-level return, or a return assuming several symbols/positions held
  concurrently?
- Is this target meant to apply to **every** trading day, or as an **average**
  across all trading days (the way it's measured above)? The two are very
  different bars -- every validated method so far has plenty of zero-trade or
  small-loss days mixed with better days.
- "First target" implies more are coming -- happy to add Target 2, 3, ... to
  this same document as they're defined (e.g. a net-of-cost version of this
  same target, once Stage 11 produces a candidate worth cost-testing; a
  maximum-drawdown ceiling; a minimum Sharpe or Deflated Sharpe floor per
  Stage 7.7).
