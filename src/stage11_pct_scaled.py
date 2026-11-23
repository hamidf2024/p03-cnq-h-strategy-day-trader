"""
Stage 11, secondary candidate: percent-of-price-scaled version of the
existing V7.1 intraday zone-bounce rule, instead of its fixed-DOLLAR stop/
target (0.10/0.20 normal, 0.15/0.30 wide day). Motivation (from the
quantitative feasibility check, see stage11_swing_breakout.py's docstring
and the Stage 11 write-up): CNQ's price rose ~4.6x from 2020 (~$9.9 avg) to
2026 (~$45.6 avg) across this dataset, while V7/V7.1's stop/target stayed
fixed in cents -- so the SAME nominal target became a much smaller percent
move in later years, which is one concrete, data-grounded reason the
project's own "Avg gross %/trade" figures are so small. This candidate asks
one narrow question: does simply re-expressing the existing, already-
validated V7.1 entry/exit RULE LOGIC with a percent-of-entry-price stop/
target (instead of fixed cents) change the picture -- while changing
nothing else (same zones, same confirmation logic, same walk-forward
discipline as Stage 10)?

normal_stop/normal_tp/wide_stop/wide_tp are reparameterized as PERCENTAGES
of each trade's own entry price, computed inside run_version_pct() (a thin
wrapper that monkeypatches bt7's stop/tp from % to $ at runtime per-entry
-- see below). Percentages are derived from the ORIGINAL cent values at
the dataset's STARTING price level (~$9.86, 2020 avg close) purely as a
reference point for the base percentage, so the comparison starts from
the project's own already-validated numbers rather than an arbitrary new
guess: normal_stop_pct = 0.10/9.86, normal_tp_pct = 0.20/9.86, wide_stop_pct
= 0.15/9.86, wide_tp_pct = 0.30/9.86. This is one candidate among several
possible percent levels -- a 2x2 small grid (normal_tp_pct in {2x, 4x} the
base derived value) is walk-forward tested, same MIN_TRADES=30 floor and
fold structure as Stage 10, band/cutoff frozen at V7.1's existing final
Stage-10-selected values (band=0.02, cutoff=12:55) to isolate the effect of
percent-scaling alone, not re-mix it with Stage 10's already-settled grid
search.
"""
import sys, json
sys.path.insert(0, '.')
import pandas as pd
import numpy as np

BASE_PRICE = 9.86  # 2020 avg close, the reference level V7.1's cent offsets were effectively tuned against (32-day window traded around $9-13)
BASE_STOP_PCT = 0.10 / BASE_PRICE
BASE_TP_PCT = 0.20 / BASE_PRICE
BASE_WIDE_STOP_PCT = 0.15 / BASE_PRICE
BASE_WIDE_TP_PCT = 0.30 / BASE_PRICE

import bt7_unified_backtester_v1_to_v71 as bt7

def run_version_pct(cfg, test_days, tp_mult=1.0, stop_mult=1.0, ref_price=None):
    """Runs bt7's run_version but with stop/tp computed as a % of price
    rather than fixed dollars. bt7.run_version takes ONE fixed dollar
    offset for all days passed to it in a single call (it has no concept
    of a per-day or per-trade offset) -- reproducing a true per-TRADE
    percent offset would require forking run_version's ~300-line loop
    just to change 4 arithmetic lines, which risks introducing a subtle
    behavioral divergence from the already-validated V7.1 logic. Instead,
    this uses one FIXED reference price per call (ref_price, supplied by
    the caller as the PRIOR calendar year's average close -- never the
    test year's own data, so there is no look-ahead) to convert the
    percent targets to a single dollar amount for that whole year, then
    calls bt7.run_version exactly once per (grid candidate, year) with
    that dollar amount -- i.e. "what V7.1 would look like if its cent
    offsets had been re-set at the start of each year to match that
    year's starting price level," rather than a true live per-trade
    percent (a stated, scoped simplification, cheap enough to walk-
    forward test; a full per-trade percent implementation is flagged as
    a follow-up if this coarser version shows anything promising).
    """
    cfg_year = dict(cfg)
    cfg_year['normal_stop'] = BASE_STOP_PCT * stop_mult * ref_price
    cfg_year['normal_tp'] = BASE_TP_PCT * tp_mult * ref_price
    cfg_year['wide_stop'] = BASE_WIDE_STOP_PCT * stop_mult * ref_price
    cfg_year['wide_tp'] = BASE_WIDE_TP_PCT * tp_mult * ref_price
    return bt7.run_version(cfg_year, test_days)


def dollar100_stats(trades):
    n = len(trades)
    if n == 0:
        return dict(n=0, gross_pct_avg=0.0, win_rate=0.0, pf=0.0, net_at1c_avg=0.0)
    d100 = [100.0 * (t['pnl'] / t['entry_price']) for t in trades]
    wins = [x for x in d100 if x > 0]
    losses = [x for x in d100 if x < 0]
    gross_win = sum(wins); gross_loss = -sum(losses)
    pf = gross_win / gross_loss if gross_loss > 0 else (float('inf') if gross_win > 0 else 0.0)
    wr = len(wins) / max(1, len(wins) + len(losses)) * 100
    d100_1c = [100.0 * ((t['pnl'] - 0.01) / t['entry_price']) for t in trades]
    return dict(n=n, gross_pct_avg=sum(d100)/n, win_rate=wr, pf=pf, net_at1c_avg=sum(d100_1c)/n)


MIN_TRADES = 30
TRAIN_YEARS = ['2020','2021','2022','2023']
TEST_YEARS = ['2024','2025','2026']
FOLDS = [('fold1', ['2020'], '2021'), ('fold2', ['2020','2021'], '2022'), ('fold3', ['2020','2021','2022'], '2023')]
GRID = [(1.0, 1.0), (1.0, 2.0), (1.0, 4.0)]  # (stop_mult, tp_mult) relative to BASE_*_PCT

year_days = {y: [d for d in bt7.days if str(d)[:4] == y] for y in TRAIN_YEARS + TEST_YEARS}

# Reference price per year = PRIOR calendar year's average Close (never the
# test year's own data -- no look-ahead). 2020 (first year in the data,
# no prior year available) bootstraps off its own first 20 trading days,
# the only exception, clearly flagged.
ALL_YEARS_SORTED = ['2020','2021','2022','2023','2024','2025','2026']
_year_avg_close = {}
for y in ALL_YEARS_SORTED:
    ds = [d for d in bt7.days if str(d)[:4] == y]
    closes = [bt7.day_rows[d].Close.mean() for d in ds]
    _year_avg_close[y] = sum(closes) / len(closes) if closes else None

ref_price_for_year = {}
for i, y in enumerate(ALL_YEARS_SORTED):
    if i == 0:
        ds0 = [d for d in bt7.days if str(d)[:4] == y][:20]
        closes0 = [bt7.day_rows[d].Close.mean() for d in ds0]
        ref_price_for_year[y] = sum(closes0) / len(closes0)
    else:
        ref_price_for_year[y] = _year_avg_close[ALL_YEARS_SORTED[i-1]]

V71_BASE = dict(exit_mode='next_zone', or_zone='exit_only', weak_fn='strong_green',
                 band=0.02, wide_day_threshold=0.40, entry_cutoff='12:55', avg_lookback=10,
                 max_attempts=999, ratchet_stop=True, ratchet_buffer=0.0,
                 wick_require_above_open=True)


def trades_cache():
    cache = {}
    for (sm, tm) in GRID:
        for y in TRAIN_YEARS + TEST_YEARS:
            cache[(sm, tm, y)] = run_version_pct(V71_BASE, year_days[y], tp_mult=tm, stop_mult=sm,
                                                   ref_price=ref_price_for_year[y])
    return cache


def best_by_net_pct(cache, years):
    best = None
    for (sm, tm) in GRID:
        trades = []
        for y in years:
            trades.extend(cache[(sm, tm, y)])
        if len(trades) < MIN_TRADES:
            continue
        s = dollar100_stats(trades)
        if best is None or s['gross_pct_avg'] > best[0]:
            best = (s['gross_pct_avg'], sm, tm, s, len(trades))
    return best


def main():
    cache = trades_cache()
    out = {'folds': {}}
    for name, train_years, val_year in FOLDS:
        picked = best_by_net_pct(cache, train_years)
        if picked is None:
            out['folds'][name] = {'note': 'no candidate cleared floor'}
            continue
        npt, sm, tm, s_train, n_train = picked
        val_trades = cache[(sm, tm, val_year)]
        s_val = dollar100_stats(val_trades)
        out['folds'][name] = dict(train_years=train_years, val_year=val_year,
                                    chosen_stop_mult=sm, chosen_tp_mult=tm,
                                    train=s_train, val=s_val)
    picked = best_by_net_pct(cache, TRAIN_YEARS)
    npt, sm, tm, s_train, n_train = picked
    out['final'] = dict(chosen_stop_mult=sm, chosen_tp_mult=tm, train=s_train)
    out['test'] = {}
    for y in TEST_YEARS:
        out['test'][y] = dollar100_stats(cache[(sm, tm, y)])
    combined = []
    for y in TEST_YEARS:
        combined.extend(cache[(sm, tm, y)])
    out['test']['combined'] = dollar100_stats(combined)
    with open('../stage11_pct_scaled_results.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps(out, indent=2, default=str))


if __name__ == '__main__':
    main()
