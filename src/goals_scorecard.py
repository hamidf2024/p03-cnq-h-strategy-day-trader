"""
Goal scorecard: every model/method in the project, scored against the goal
ladders the owner added to the charter on 2026-11-23, on the blind years
2024-2026 and with $1,000 invested per trade.

    G   average gross % per trade          G1 >= 1%    G2 >= 2%    G3 > 3%
    WR  win rate                           WR1 >= 50%  WR2 >= 65%  WR3 > 75%
    S   steadiness: months in each year    S1 8 of 12  S2 10 of 12 S3 12 of 12
        whose gross % for the month is
        above 1%

Nothing is tuned here. Each method is re-run with the configuration that was
already frozen in its own stage, only to obtain a per-trade list from which
the win rate and the month-by-month figures can be computed.

Two steps
---------
1. build   (needs the local price file; slow)
   Run in a working folder that holds cnq.csv (the local
   data/raw/CNQ_5min_20200727_to_20261118.csv) and copies of
   bt7_unified_backtester_v1_to_v71.py, ml_v8_gbm_experiment.py,
   stage10_walk_forward_training.py and stage11_pct_scaled.py:
       python3 goals_scorecard.py build rules    # V1-V6, V7, V7.1, percent-scaled V7.1
       python3 goals_scorecard.py build ml       # Rule OR Model
   Writes goals_trades_rules.csv / goals_trades_ml.csv (per-trade lists; these
   contain prices and stay local).
2. score   (no price data needed)
       python3 goals_scorecard.py score <trade csv> [<trade csv> ...] \
           --stage11 results/experiments/stage11_swing_results.json \
           --stage12 results/experiments/stage12_blind_trades.csv \
           --out results/experiments
   Writes goals_scorecard.json and goals_monthly_2024_2026.csv (no prices).

Definitions
-----------
* Gross % of a trade = profit per share / entry price x 100, before costs.
  With $1,000 invested in each trade the profit in dollars is 10 x that.
* Win rate = wins / (wins + losses); a trade within half a cent per share of
  zero is a scratch and is left out (the project's convention since V1). The
  same-day methods have many scratches, so the share of ALL trades that made
  money is reported beside it (wins_share_of_all_trades), and the top five is
  also worked out with that stricter number (top5_if_scratch_is_not_a_win).
* Profit factor = total of winning trades' gross % / total of losing trades'
  gross %, i.e. on equal dollars per trade.
* Gross % for a month = the sum of the gross % of the trades opened in that
  month, i.e. the month's profit as a share of a $1,000 stake that is put to
  work again on each trade (not compounded). A month with no trade is 0%.
* Steadiness is counted per calendar year. 2026 runs to 18 November, so it has
  11 months; its count is compared with the same fractions (8/12, 10/12, 12/12).
  A level counts as reached only if it is reached in every blind year.
* Cost check: 1 cent per share for the round trip (spread and slippage; both
  brokers the owner uses charge no commission).
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

BLIND = ('2024', '2025', '2026')
STAKE = 1000.0
G_LEVELS = (1.0, 2.0, 3.0)
WR_LEVELS = (50.0, 65.0, 75.0)
S_LEVELS = (8 / 12, 10 / 12, 12 / 12)
MONTHS_IN_YEAR = {2024: 12, 2025: 12, 2026: 11}      # data ends 2026-11-18
MIN_TRADES_FOR_RANK = 15

META = {   # id: (display name, family, holding, stage, how the settings were chosen)
    'V1': ('V1', 'Intraday zone rule', 'same day', 1, 'original hand-set rules'),
    'V2': ('V2', 'Intraday zone rule', 'same day', 2, 'original hand-set rules'),
    'V3': ('V3', 'Intraday zone rule', 'same day', 3, 'original hand-set rules'),
    'V4': ('V4', 'Intraday zone rule', 'same day', 4, 'original hand-set rules'),
    'V5': ('V5', 'Intraday zone rule', 'same day', 5, 'original hand-set rules'),
    'V6': ('V6', 'Intraday zone rule', 'same day', 6, 'original hand-set rules'),
    'V7_wf': ('V7', 'Intraday zone rule', 'same day', 10, 'walk-forward on 2020-2023'),
    'V7.1_wf': ('V7.1', 'Intraday zone rule', 'same day', 10, 'walk-forward on 2020-2023'),
    'RuleOrModel': ('Rule OR Model', 'Intraday rule + ML', 'same day', 10, 'walk-forward on 2020-2023'),
    'V7.1_pct': ('V7.1 percent-scaled', 'Intraday zone rule', 'same day', 11, 'walk-forward on 2020-2023'),
    'Donchian_long': ('Donchian swing, long-only', 'Swing trend rule', 'weeks', 11, 'walk-forward on 2020-2023'),
    'Donchian_ls': ('Donchian swing, long+short', 'Swing trend rule', 'weeks', 11, 'walk-forward on 2020-2023'),
    'A_spring_release': ('A. Spring-release', 'Swing physics rule', '5 days', 12, 'walk-forward on 2020-2023'),
    'B_field_fusion_gbm': ('B. Field-Fusion GBM', 'Swing ML model', '5 days', 12, 'walk-forward on 2020-2023'),
    'C_transformer_probe': ('C. Transformer probe', 'Swing ML model', '5 days', 12, 'walk-forward on 2020-2023'),
    'D_fusion_gate': ('D. Fusion gate', 'Swing rule + ML', '5 days', 12, 'walk-forward on 2020-2023'),
}


# ------------------------------------------------------------------- build
def build_rules():
    import bt7_unified_backtester_v1_to_v71 as bt7
    from stage10_walk_forward_training import METHOD_BASE
    import stage11_pct_scaled as s11
    days = [d for d in bt7.days if str(d)[:4] in BLIND]
    out = []

    def add(mid, trades):
        for t in trades:
            out.append(dict(method=mid, entry_date=str(t['date']), entry_price=float(t['entry_price']), pnl=float(t['pnl'])))
        s = bt7.stats(trades)
        g = np.mean([100 * t['pnl'] / t['entry_price'] for t in trades])
        print(f'{mid:12s} n={s["n"]:5d} win_rate={s["win_rate_excl"]:.1f}% pf={s["pf"]:.2f} net={s["net"]:+.3f} gross%={g:.4f}', flush=True)
        pd.DataFrame(out).to_csv('goals_trades_rules.csv', index=False)

    # regression check first: hand-set V7.1 by year must match Stage 9
    chk = bt7.run_version(bt7.VERSIONS['V7.1'], days)
    by = {}
    for t in chk:
        by.setdefault(str(t['date'])[:4], []).append(t)
    got = {y: (len(v), round(bt7.stats(v)['win_rate_excl'], 1)) for y, v in by.items()}
    want = {'2024': (571, 60.8), '2025': (618, 60.0), '2026': (491, 57.3)}
    print('regression check (hand-set V7.1 by year vs Stage 9):', got, 'PASS' if got == want else 'FAIL', flush=True)
    assert got == want, 'price file does not reproduce Stage 9'

    for v in ('V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
        add(v, bt7.run_version(bt7.VERSIONS[v], days))
    for m in ('V7', 'V7.1'):                       # Stage 10 frozen configuration
        cfg = dict(METHOD_BASE[m]); cfg['band'] = 0.02; cfg['entry_cutoff'] = '12:55'
        add(m + '_wf', bt7.run_version(cfg, days))
    tr = []                                        # Stage 11 frozen configuration (1x stop, 1x target)
    for y in BLIND:
        tr += s11.run_version_pct(s11.V71_BASE, s11.year_days[y], tp_mult=1.0, stop_mult=1.0, ref_price=s11.ref_price_for_year[y])
    add('V7.1_pct', tr)
    print('rules done', flush=True)


def build_ml():
    import stage10_walk_forward_training as s10
    from ml_v8_gbm_experiment import prep, run_sequential
    cand = s10.build_candidate_cache()
    train = pd.concat([cand[y] for y in s10.TRAIN_YEARS], ignore_index=True)
    clf, cols, thr = s10.pick_threshold_and_fit(train)
    print('frozen threshold', thr, '(Stage 10: 0.350)', flush=True)
    out = []
    for y in BLIND:
        df = cand[y].copy()
        X, _ = prep(df)
        df['proba'] = clf.predict_proba(s10.align_cols(cols, X))[:, 1]
        trades = run_sequential(df, s10.combined_select_factory(thr))
        for t in trades:
            d = pd.Timestamp(t['date']).date()
            out.append(dict(method='RuleOrModel', entry_date=str(d),
                            entry_price=float(s10.day_rows[d].iloc[t['bar_idx']].Close), pnl=float(t['pnl'])))
        print(y, 'n', len(trades), flush=True)
    pd.DataFrame(out).to_csv('goals_trades_ml.csv', index=False)
    g = np.mean([100 * t['pnl'] / t['entry_price'] for t in out])
    print(f'RuleOrModel n={len(out)} gross%={g:.4f} (Stage 10: 3,890 / 0.0178)', flush=True)


# ------------------------------------------------------------------- score
def level(value, levels, top_strict=True):
    lv = 0
    if value >= levels[0]: lv = 1
    if value >= levels[1]: lv = 2
    if (value > levels[2]) if top_strict else (value >= levels[2] - 1e-12): lv = 3
    return lv


def load_trades(paths, stage11, stage12):
    frames = [pd.read_csv(p) for p in paths]
    if stage11:
        r = json.load(open(stage11))
        for key, mid in (('long_only', 'Donchian_long'), ('long_short', 'Donchian_ls')):
            rows = [dict(method=mid, entry_date=t['entry_date'][:10], entry_price=t['entry_price'], pnl=t['pnl'])
                    for t in r[key]['_final_trades_combined_detail']]
            frames.append(pd.DataFrame(rows))
    if stage12:
        t = pd.read_csv(stage12)
        frames.append(pd.DataFrame(dict(method=t.model, entry_date=t.entry_date.str[:10], entry_price=t.entry,
                                        pnl=t.ret / 100 * t.entry)))
    tr = pd.concat(frames, ignore_index=True)
    tr['entry_date'] = pd.to_datetime(tr.entry_date)
    tr = tr[tr.entry_date.dt.year.astype(str).isin(BLIND)].copy()
    tr['ret'] = tr.pnl / tr.entry_price * 100
    tr['year'] = tr.entry_date.dt.year
    tr['month'] = tr.entry_date.dt.strftime('%Y-%m')
    return tr


def score(paths, stage11, stage12, outdir):
    tr = load_trades(paths, stage11, stage12)
    all_months = [f'{y}-{m:02d}' for y in (2024, 2025, 2026) for m in range(1, MONTHS_IN_YEAR[y] + 1)]
    monthly_rows, cards = [], []
    for mid in META:
        t = tr[tr.method == mid]
        if len(t) == 0:
            continue
        name, family, holding, stage, chosen = META[mid]
        wins = int((t.pnl > 0.005).sum()); losses = int((t.pnl < -0.005).sum())
        wr = 100 * wins / max(1, wins + losses)
        g = float(t.ret.mean())
        net1c = float(((t.pnl - 0.01) / t.entry_price * 100).mean())
        gw = t.ret[t.ret > 0].sum(); gl = -t.ret[t.ret < 0].sum()      # on equal dollars per trade
        wr_all = 100 * wins / len(t)
        cost_per_trade = float((0.01 / t.entry_price * STAKE).mean())    # 1 cent/share on a $1,000 position
        msum = t.groupby('month').ret.sum().reindex(all_months, fill_value=0.0)
        mcnt = t.groupby('month').size().reindex(all_months, fill_value=0)
        for m in all_months:
            mt = t[t.month == m]
            monthly_rows.append(dict(method=mid, month=m, trades=int(mcnt[m]), wins=int((mt.pnl > 0.005).sum()),
                                     losses=int((mt.pnl < -0.005).sum()), gross_pct=round(float(msum[m]), 4),
                                     dollars_per_1000=round(float(msum[m]) * STAKE / 100, 2)))
        by_year = {}
        for y in (2024, 2025, 2026):
            ty = t[t.year == y]
            ms = msum[[m for m in all_months if m.startswith(str(y))]]
            wy = int((ty.pnl > 0.005).sum()); ly = int((ty.pnl < -0.005).sum())
            by_year[y] = dict(trades=int(len(ty)), gross_pct_per_trade=round(float(ty.ret.mean()), 4) if len(ty) else None,
                              win_rate=round(100 * wy / max(1, wy + ly), 1) if (wy + ly) else None,
                              months=int(len(ms)), months_above_1pct=int((ms > 1.0).sum()),
                              months_positive=int((ms > 0).sum()), months_no_trades=int((mcnt[ms.index] == 0).sum()),
                              gross_pct_year=round(float(ms.sum()), 2), dollars_year=round(float(ms.sum()) * STAKE / 100, 2))
        frac = {y: by_year[y]['months_above_1pct'] / by_year[y]['months'] for y in by_year}
        s_frac_min = min(frac.values()); s_frac_avg = float(np.mean(list(frac.values())))
        g_lv = level(g, G_LEVELS); wr_lv = level(wr, WR_LEVELS); s_lv = level(s_frac_min, S_LEVELS, top_strict=False)
        prog_g = float(np.clip(g / G_LEVELS[2], 0, 1)); prog_wr = float(np.clip(wr / WR_LEVELS[2], 0, 1)); prog_s = float(s_frac_avg)
        cards.append(dict(
            id=mid, name=name, family=family, holding=holding, stage=stage, settings=chosen,
            trades=int(len(t)), trades_per_year=round(len(t) / 2.88, 1),
            gross_pct_per_trade=round(g, 4), dollars_per_trade=round(g * STAKE / 100, 2),
            median_pct_per_trade=round(float(t.ret.median()), 4),
            win_rate=round(wr, 1), wins=wins, losses=losses, scratches=int(len(t) - wins - losses),
            wins_share_of_all_trades=round(wr_all, 1),
            cost_1c_dollars_per_trade=round(cost_per_trade, 3), cost_1c_dollars_total=round(cost_per_trade * len(t), 2),
            shares_per_1000_avg=round(float((STAKE / t.entry_price).mean()), 1),
            profit_factor=round(float(gw / gl), 2) if gl > 0 else None,
            gross_pct_total=round(float(t.ret.sum()), 2), dollars_total=round(float(t.ret.sum()) * STAKE / 100, 2),
            net_pct_per_trade_after_1c=round(net1c, 4), dollars_per_trade_after_1c=round(net1c * STAKE / 100, 2),
            dollars_total_after_1c=round(net1c * len(t) * STAKE / 100, 2), profitable_after_1c=bool(net1c > 0),
            months_above_1pct_total=int((msum > 1.0).sum()), months_total=len(all_months),
            months_above_1pct_avg_per_12=round(12 * s_frac_avg, 1), months_above_1pct_worst_year_per_12=round(12 * s_frac_min, 1),
            avg_month_gross_pct=round(float(msum.mean()), 3),
            by_year=by_year, G_level=g_lv, WR_level=wr_lv, S_level=s_lv, levels_total=g_lv + wr_lv + s_lv,
            progress=dict(G=round(prog_g, 3), WR=round(prog_wr, 3), S=round(prog_s, 3),
                          overall=round((prog_g + prog_wr + prog_s) / 3, 3),
                          overall_if_scratch_is_not_a_win=round((prog_g + float(np.clip(wr_all / WR_LEVELS[2], 0, 1)) + prog_s) / 3, 3)),
            enough_trades_to_rank=bool(len(t) >= MIN_TRADES_FOR_RANK)))
    ranked = sorted([c for c in cards if c['enough_trades_to_rank']], key=lambda c: -c['progress']['overall'])
    for i, c in enumerate(ranked):
        c['rank'] = i + 1
    strict = sorted([c for c in cards if c['enough_trades_to_rank']], key=lambda c: -c['progress']['overall_if_scratch_is_not_a_win'])
    out = dict(
        goals=dict(G=dict(name='Average gross % per trade', levels=['>= 1%', '>= 2%', '> 3%']),
                   WR=dict(name='Win rate', levels=['>= 50%', '>= 65%', '> 75%']),
                   S=dict(name='Months per year with gross % for the month above 1%', levels=['8 of 12', '10 of 12', '12 of 12'])),
        basis=dict(period='blind 2024-01-02 to 2026-11-18', stake_per_trade=STAKE, months_counted=MONTHS_IN_YEAR,
                   ranking='overall progress = average of three fractions: gross % per trade / 3%, win rate / 75%, '
                           'share of months above 1% (each capped at 1); methods with fewer than '
                           f'{MIN_TRADES_FOR_RANK} blind trades are not ranked'),
        top5=[c['id'] for c in ranked[:5]],
        top5_if_scratch_is_not_a_win=[c['id'] for c in strict[:5]],
        leaders=dict(G=max(cards, key=lambda c: c['gross_pct_per_trade'])['id'],
                     WR=max([c for c in cards if c['enough_trades_to_rank']], key=lambda c: c['win_rate'])['id'],
                     S=max(cards, key=lambda c: c['progress']['S'])['id']),
        methods=cards)
    os.makedirs(outdir, exist_ok=True)
    json.dump(out, open(os.path.join(outdir, 'goals_scorecard.json'), 'w'), indent=1)
    pd.DataFrame(monthly_rows).to_csv(os.path.join(outdir, 'goals_monthly_2024_2026.csv'), index=False)
    pd.set_option('display.width', 250)
    show = pd.DataFrame([{**{k: c[k] for k in ('name', 'trades', 'gross_pct_per_trade', 'win_rate', 'months_above_1pct_total',
                                                'months_above_1pct_worst_year_per_12', 'G_level', 'WR_level', 'S_level',
                                                'net_pct_per_trade_after_1c', 'dollars_total')},
                          'overall': c['progress']['overall'], 'rank': c.get('rank')} for c in cards])
    print(show.to_string(index=False))
    print('top 5:', out['top5'], '| strict:', out['top5_if_scratch_is_not_a_win'], '| leaders:', out['leaders'])


if __name__ == '__main__':
    if len(sys.argv) >= 3 and sys.argv[1] == 'build':
        sys.path.insert(0, '.')
        build_rules() if sys.argv[2] == 'rules' else build_ml()
    elif len(sys.argv) >= 2 and sys.argv[1] == 'score':
        ap = argparse.ArgumentParser()
        ap.add_argument('cmd'); ap.add_argument('trades', nargs='*')
        ap.add_argument('--stage11'); ap.add_argument('--stage12'); ap.add_argument('--out', default='results/experiments')
        a = ap.parse_args()
        score(a.trades, a.stage11, a.stage12, a.out)
    else:
        print(__doc__)
