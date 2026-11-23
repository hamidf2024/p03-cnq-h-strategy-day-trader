# Goals & Targets

*Added 2026-11-23, at the owner's direction ("define target and goals for this
project; first target and goal is developing a model/method which can have 1%
gross per day"). This document sits alongside `00_Project_Charter.docx` (the
project's original objective and priority order) and `01_Phases_of_Development.docx`
(the stage-by-stage roadmap) rather than replacing them: the charter's priority
order is kept below as a guardrail, and this file adds the first concrete,
numeric performance target the project is now aimed at.*

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
