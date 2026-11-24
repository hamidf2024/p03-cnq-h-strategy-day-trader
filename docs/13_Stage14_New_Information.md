# Stage 14: new information (2026-11-24)

*Project 3, CNQ. Continues `12_Stage13_Peer_Fusion_Research.md`. Goals and
scorecard: `07_Goals_and_Targets.md`.*

## Summary

Stage 13 ended with every arrangement of the same price data tried and no
model at level 1 on all four goals. Stage 14 adds information the models
never had: eighteen more symbols from the same source. On the training years
(2021-2023, test years removed from the data):

- **The new information improves the month-ahead forecast.** At 20 sessions
  the out-of-sample rank correlation between forecast and return rises from
  0.114 to 0.166 for CNQ and from 0.056 to 0.109 across the six stocks. At 5
  sessions it makes little or no difference.
- **A monthly campaign timed by that forecast (model R) does better than the
  same campaign timed by the old forecast in all eight settings**, for
  example +1.58% against +0.85% per trade.
- **No setting passes the gate, so nothing was run on 2024-2026.** The
  closest setting fails one part and the next two fail two. The count of
  runs on the test years stays at 22.

## 1. Data

Downloaded by the owner on 2026-11-23/24 with
`src/stage13_download_peer_oil_data.py all`; 5-minute consolidated-feed bars,
2020-07-27 to 2026-11-23, kept only in the local `data/raw/peers/` folder.

| Group | Symbols | What it adds |
|---|---|---|
| Oil curve | USL (12-month oil fund), read against USO | slope of the oil futures curve |
| Brent | BNO, read against USO | Brent-WTI gap |
| Natural gas | UNG | CNQ produces gas as well as oil |
| Refining | VLO, MPC, PSX, read against XOP | refining margin |
| Producers, services | XOP, OIH | sector breadth |
| Pipelines | ENB, TRP | Canadian energy |
| Currency | FXC (Canadian dollar), UUP (US dollar) | exchange rate |
| Markets | SPY, EWC (Canada), VIXY (volatility), TLT, HYG, GLD | market, risk appetite |

Checks (`results/experiments/stage14_data_checks.json`): all 26 files cover
the full period; no empty cells, no zero or negative prices, no zero-volume
bars, no duplicate timestamps. USL and FXC trade thinly (about a third of the
bars exist) and are used as daily prices only. The three known vendor gap
days appear again for some symbols. The eight Stage 13 files were refreshed
in the same run; model P reproduces identically on the refreshed CNQ file.

## 2. Does the new information help? (`src/stage14_information_test.py`)

51 new daily features, all known at 15:50 (`src/stage14_lib.py`), added to
the 57 from Stage 13. Same pooled gradient-boosted model, settings and seeds
as model E. Walk-forward: each of 2021, 2022, 2023 is predicted by a model
trained only on earlier rows, with the label horizon purged.

Rank correlation of forecast with realised forward return, out of sample:

| Horizon | Scope | Old features | Old + new | Top fifth minus bottom fifth, old -> new |
|---|---|---|---|---|
| 5 sessions | CNQ | 0.059 | 0.067 | +0.67% -> +1.14% |
| 5 sessions | six stocks | 0.054 | 0.029 | +0.78% -> +0.52% |
| 20 sessions | CNQ | 0.114 | **0.166** | +3.17% -> +5.31% |
| 20 sessions | six stocks | 0.056 | **0.109** | +2.26% -> +4.29% |

By year at 20 sessions for CNQ: 2021 0.126 -> 0.252, 2022 0.145 -> 0.101,
2023 0.174 -> 0.255. The new features carry about 60% of the model's
importance; the most used are the credit spread (high-yield against long
bonds), oil services against producers, the Brent-WTI gap, the US dollar and
the stock's market beta.

Cautions. Twenty-session returns overlap, so 750 days hold about 37
independent periods; the market-wide features are the same for all six
stocks on a day, so pooling adds less than it seems; the 2021 fold is trained
on about two months of data.

## 3. Model R: a campaign timed by the month-ahead forecast (`src/stage14_macro_fusion.py`)

Each month, the first day the 20-session forecast's trailing rank is at least
q; two $1,000 buys at different times; target, 15% stop, 60 sessions.

**Gate, fixed before the campaign was computed:** (A) one spare month on S
and GM in every training year, counted on the months in which a signal was
possible (2021 starts in March: 10 months), G at least 1.25%, win rate at
least 55%; (B) better than buying after every day with the same exit in
every year; (C) the same campaign on each of the six stocks, with its own
forecasts, reaches level 1 in 14 of 18 stock-years; (D) still level 1 with
the buys shifted to other times; (E) better than the same campaign timed by
the old-feature forecast.

| q | Target | Buys | Trades | G | Win rate | S | GM | Parts passed |
|---|---|---|---|---|---|---|---|---|
| 0.5 | 3% | 10:00 and 13:00 next day | 60 | +1.58% | 91.7% | 8 / 10 / 9 | 8 / 10 / 9 | A, C, E |
| 0.5 | 3% | close and 10:00 next day | 60 | +1.58% | 91.7% | 8 / 9 / 10 | 8 / 9 / 10 | A, C, E |
| 0.5 | 4% | 10:00 and 13:00 next day | 60 | +1.45% | 86.7% | 7 / 9 / 9 | 7 / 9 / 8 | D, E |
| 0.5 | 4% | close and 10:00 next day | 60 | +1.71% | 86.7% | 8 / 9 / 7 | 8 / 9 / 7 | B, C, D, E |
| 0.7 | 3% or 4% | either | 50 | +1.27% to +1.30% | 86% to 90% | 6 / 6-7 / 8-10 | 6 / 6-7 / 8-10 | E |

(Need: 7 / 8 / 7 months.)

**Result: no setting passes all five parts; nothing was frozen and no run on
2024-2026 was made.** The best 3% settings fail B (in 2021 the timing made
0.07% to 0.12% less than buying every day) and D (with buys at 13:00 and the
close the average falls to +0.94%). The best 4% setting fails only A: 2023
has exactly the 7 months it needs, with none to spare.

Part E passes in all eight settings: timed by the new forecast the campaign
makes more than timed by the old one (for the 3% settings +1.58% against
+0.85% and +0.78%). That is the first evidence in the project that new
information, rather than a new arrangement of trades, moves the result.

## 4. What this means and what comes next

The direction is right and the size is not yet enough. The forecast is better
at the horizon the goals need (a month), and the campaign built on it is
better than the Stage 13 campaigns on the training years, but it does not
clear a gate that was built to stop models like N and P.

Next steps, in order:

1. Improve the forecast, not the gate: labels that match the exit (did the
   price reach the target before the stop), more years of the new symbols if
   the source allows a start before 2020, and the calendar of oil-inventory
   reports and CNQ's earnings and dividend dates.
2. Forward test of the frozen models M, O and L on trades after 2026-11-20
   (`results/experiments/forward_test_manifest.json`).
3. Any model that passes the gate gets one run on 2024-2026, which would be
   run 23.

## 5. Leak check, repeated on all 108 features (2026-11-24)

Asked by the owner: confirm that no test-year data was used to build or
design the models. Two different things are involved.

**Data leak (checked, none found).** `src/stage14_leak_check.py`,
`results/experiments/stage14_leak_check.json`:

- Every feature (57 from Stage 13, 51 from Stage 14) was rebuilt from three
  versions of the data: all of it, cut at 2023-12-29, and cut at 2025-06-30.
  On every day the shorter versions contain, all 108 features are identical
  to the full version (5,184 and 7,428 rows; largest difference 0.0). The
  first comparison shows the training rows never saw 2024-2026; the second
  shows that inside the test years a day's features never use a later day.
- The frozen Peer-Fusion model was last trained on 2023-12-21 and its labels
  reach 2023-12-29. Out-of-fold forecasts run from 2021-01-04 to 2023-12-29.
- Every selection after model M (rounds 11 to 15 and Stage 14) was run with
  the test years removed from the data at load, and the code stops if a
  later day is present.
- Models M, O and P were re-run from their frozen files on the refreshed
  download and reproduced their published results exactly.

**Design influence (present, cannot be removed).** The person choosing what
to build next had seen earlier test results. E to H were fixed before any of
them was run. Every model from I onward (I, J, K, L, M, N, O, P, Q, R) was
designed after earlier results on 2024-2026 were known: J after I, M after
J, P after the stops of N and M, and so on. V1 to V6 use rules set by hand
on weeks in mid-2026, inside the test period. This is not a data leak, but
it means the later results are less independent than the first ones, which
is why the count of runs (22) is published and why the forward test on
trades after 2026-11-20 is the confirmation that counts.

## 6. Can goal 4 in its current form be reached at all? (2026-11-24)

Goal 4 now asks, in every year, for 8 months whose trades total 5% or more
and at most one losing month, no worse than -2%. Before building another
model, `src/s14_goal4_feasibility.py` (results in
`results/experiments/stage14_goal4_feasibility.json`) asked whether any design
in a wide family could meet it together with G1, WR1 and S1 on the training
years, with the test years removed from the data.

The family: enter at the close of every day the forecast (5- or 20-session,
old or old + new features, out of fold) is in the top half, 30% or 15%;
$1,000 per entry; up to 1, 3 or 5 open at once; target 1-4%; stop 1, 2, 3,
5 or 15%; 5, 10 or 20 sessions; with and without closing every trade by the
end of its month; with and without a monthly loss budget that stops new
entries once a month's trades have lost 1.5%. **8,627 settings.** They were
scored on the same years they were picked on, so this is an upper bound: a
design that cannot pass here cannot pass honestly.

**Result: none of the 8,627 reaches level 1 on all four goals in every
training year. Only 44 keep goal 4 in even one year, and none in two.** Every
setting has at least one losing month in its worst year, and almost always a
month far below -2%: a stopped trade loses 1-15% at once, and several trades
opened in the same month on the same stock go down together.

For comparison, simply holding CNQ had 4 to 6 losing months a year in
2021-2023, three of them below -2% in every year.

What it means: a year with at most one small losing month and eight months
of +5% is the profile of a strategy whose monthly result almost never dips.
Trades in one stock over a few days or weeks move together and lose in the
same slides, so adding more of them in a month raises the gains and the
losses together. On the training years no design in this family comes close,
so no new model was run on 2024-2026 (still 22 runs). The forward test of the
frozen models continues.

## Code and results

`src/stage14_lib.py`, `src/stage14_information_test.py`,
`src/stage14_macro_fusion.py`, `src/stage14_leak_check.py`, `src/s14_goal4_feasibility.py`;
`results/experiments/stage14_data_checks.json`, `stage14_leak_check.json`, `stage14_goal4_feasibility.json`,
`stage14_information_test.json`, `stage14_macro_fusion_selection.json`. The
out-of-fold forecasts (`stage14_oof_predictions_LOCAL_ONLY.pkl`) hold forward
returns and stay in the local folder.
