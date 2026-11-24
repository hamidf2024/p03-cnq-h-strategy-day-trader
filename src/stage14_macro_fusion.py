"""
Stage 14: model R, a monthly campaign timed by a month-ahead forecast that uses new information.

Step 1 (stage14_information_test.py, training years only) showed that the Stage 14 features (oil curve,
Brent-WTI gap, natural gas, refining margin, currency, market, volatility, credit) do not improve a 5-session
forecast but do improve a 20-session one: out-of-sample rank correlation for CNQ 0.114 -> 0.166, for all six
stocks 0.056 -> 0.109. Model R uses that 20-session forecast to choose the day of each month's entry.

    forecast  pooled gradient-boosted model (Stage 13 settings and seeds) on 57 old + 51 new features,
              label = 20-session forward return, standardised; walk-forward on 2021, 2022, 2023
    signal    each month, the first day on which the forecast's trailing rank (share of the last 120
              forecasts below today's) is at least q; if no such day, no trade that month
    buys      two $1,000 buys at different times (one of two fixed patterns)
    exit      target, 15% stop, 60 sessions, each buy on its own

Modes
    select   training years only; needs S13_CUTOFF=2023-12-29 and the out-of-fold forecasts from step 1
    dry      rehearses the blind code on 2023 with the test years removed; writes nothing
    blind    one run on 2024-2026 of the frozen setting; refuses to run twice
    verify   reproduces the stored blind result

GATE (fixed before the campaign was computed)
 A. CNQ, each of 2021, 2022, 2023: S >= need + 1 and GM >= need + 1, where need = 8/12 of the months in which
    a signal was possible, rounded up (the rank needs 40 earlier forecasts, so 2021 starts in March: 10 months;
    2023 ends where a 60-session hold still fits). Over the three years G >= 1.25% and win rate >= 55%.
 B. Timing must add something: G minus "buy after every day, same buys and exit" above zero in EVERY year.
 C. Peers: the same campaign on each of the six stocks with that stock's own forecasts reaches S >= need and
    GM >= need in at least 14 of 18 stock-years, with at least 1.0% per trade across all six.
 D. Entry shift: with the buys moved to the other pattern and to "13:00 and close of the next session", CNQ
    still reaches S >= need and GM >= need in every year and G >= 1.0%.
 E. The new information must be the reason: the same campaign timed by the OLD-feature 20-session forecast
    must have a lower G.
 Reported beside the result: break-even win rate of the exit, and how many settings pass.
 Choice among passers: largest worst-year margin on the month goals, then peer stock-years, then G.
 If nothing passes, nothing is frozen and no run on 2024-2026 is made.

Family (8 settings): q 0.5 or 0.7; target 3% or 4%; buys "10:00 and 13:00 next session" or "close and 10:00
next session".
"""
import hashlib
import json
import os
import pickle
import sys
import numpy as np
import pandas as pd
import s13_lib as L
import stage13_peer_fusion as P
import stage14_lib as S14
from stage13_two_buys import Tape

RES = os.environ.get('S13_OUT', 'results/experiments')
NAME = 'R16_macro_fusion_campaign'
ART = 'stage14_frozen_R16.pkl'
H, STOP, HOLD = 20, 15.0, 60
QS = [0.5, 0.7]; TARGETS = [3.0, 4.0]
BUYS = {'next1000+next1300': [(1, '10:00'), (1, '13:00')], 'close+next1000': [(0, 'close'), (1, '10:00')], 'next1300+nextclose': [(1, '13:00'), (1, 'close')]}
MAIN_BUYS = ['next1000+next1300', 'close+next1000']
YEARS_TRAIN = [2021, 2022, 2023]; YEARS_BLIND = [2024, 2025, 2026]; MONTHS_BLIND = {2024: 12, 2025: 12, 2026: 11}


def signal_days(pred, valid, q):
    """pred: Series date -> forecast for one stock. First day of each month whose trailing rank is >= q."""
    rk = P.trailing_rank(pred.sort_index()); out = {}
    for d, v in rk.items():
        m = (d.year, d.month)
        if m not in out and not np.isnan(v) and v >= q and valid.get(d, False):
            out[m] = d
    return list(out.values()), rk


def campaign(tape, days, buys, target, cache, first=None, last=None):
    rows = []
    for sd in days:
        if sd not in tape.pos or (first is not None and sd < first) or (last is not None and sd > last):
            continue
        i = tape.pos[sd]; seen = set()
        for off, when in BUYS[buys]:
            if i + off >= len(tape.days) - 1:
                continue
            d = tape.days[i + off]; k = tape.bar_index(d, when)
            if (d, k) in seen:
                continue
            seen.add((d, k)); key = (d, k, target)
            if key not in cache:
                cache[key] = tape.buy(d, k, HOLD, target, STOP)
            entry, xd, px, why = cache[key]; mins = tape.bars[d][0][k] + 5
            rows.append(dict(signal_day=sd, entry_date=d, entry_time=f'{mins // 60:02d}:{mins % 60:02d}', exit_date=xd, side=1, entry_price=entry,
                             exit_price=px, pnl=px - entry, ret=(px / entry - 1) * 100, reason=why, days=tape.pos[xd] - tape.pos[d]))
    cols = ['signal_day', 'entry_date', 'entry_time', 'exit_date', 'side', 'entry_price', 'exit_price', 'pnl', 'ret', 'reason', 'days']
    return pd.DataFrame(rows, columns=cols)


def month_stats(t, years, avail):
    per = {}
    for y in years:
        ty = t[t.entry_date.dt.year == y]; g = ty.groupby(ty.entry_date.dt.month).ret
        per[y] = dict(n=int(len(ty)), G=round(float(ty.ret.mean()), 3) if len(ty) else None, WR=round(float((ty.ret > 0).mean() * 100), 1) if len(ty) else None,
                      S=int((g.mean() > 1).sum()), GM=int((g.sum() >= 5).sum()), months=avail[y], need=int(np.ceil(8 / 12 * avail[y])),
                      total_pct=round(float(ty.ret.sum()), 1))
    return per


def bench_by_year(tape, valid_days, buys, target, cache, first=None, last=None):
    t = campaign(tape, valid_days, buys, target, cache, first, last)
    return t.groupby(t.entry_date.dt.year).ret.mean()


def select():
    cut = os.environ.get('S13_CUTOFF', ''); assert cut and cut <= '2023-12-31', 'run the selection with S13_CUTOFF=2023-12-29'
    panel, D, intr = P.get_panel(); cal = D['USO'].index; assert cal.max() <= pd.Timestamp('2023-12-31')
    oof = pickle.load(open(f'{RES}/stage14_oof_predictions_LOCAL_ONLY.pkl', 'rb'))
    tapes = {s: Tape(intr[s], D[s]) for s in L.STOCKS}; caches = {s: {} for s in L.STOCKS}
    valid = {s: panel[panel.stock == s].set_index('date').valid.to_dict() for s in L.STOCKS}
    end = tapes['CNQ'].days[-HOLD - 2]

    def preds(name, s):
        q = oof[(H, name)]; return q[q.stock == s].set_index('date').pred

    first_rank = P.trailing_rank(preds('NEW', 'CNQ').sort_index()).dropna().index[0]
    avail = {2021: 12 - first_rank.month + 1, 2022: 12, 2023: int(end.month)}
    print('first day with a rank:', first_rank.date(), '| months available', avail, '| last signal day', end.date(), flush=True)
    vdays = {s: [d for d in tapes[s].days if valid[s].get(d, False) and d >= first_rank and d <= end] for s in L.STOCKS}
    res = {}
    for q in QS:
        sig = {name: {s: signal_days(preds(name, s), valid[s], q)[0] for s in L.STOCKS} for name in ('NEW', 'OLD')}
        for T in TARGETS:
            runs = {b: campaign(tapes['CNQ'], sig['NEW']['CNQ'], b, T, caches['CNQ'], last=end) for b in BUYS}
            bench = {b: bench_by_year(tapes['CNQ'], vdays['CNQ'], b, T, caches['CNQ']) for b in MAIN_BUYS}
            for b in MAIN_BUYS:
                t = runs[b]; per = month_stats(t, YEARS_TRAIN, avail)
                G = float(t.ret.mean()); WR = float((t.ret > 0).mean() * 100)
                margin = min(min(p['S'], p['GM']) - p['need'] for p in per.values())
                a_ok = margin >= 1 and G >= 1.25 and WR >= 55
                ex = {y: round(float(t[t.entry_date.dt.year == y].ret.mean() - bench[b].get(y, np.nan)), 2) for y in YEARS_TRAIN}
                b_ok = all(v > 0 for v in ex.values())
                passed = 0; allr = []; xs = {}
                for s in L.STOCKS:
                    ts = campaign(tapes[s], sig['NEW'][s], b, T, caches[s], last=end); ps = month_stats(ts, YEARS_TRAIN, avail); allr.append(ts.ret)
                    xs[s] = {y: [p['S'], p['GM']] for y, p in ps.items()}
                    passed += sum(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in ps.values())
                Gx = float(pd.concat(allr).mean()); c_ok = passed >= 14 and Gx >= 1.0
                shifts = {}
                for ob in BUYS:
                    if ob == b:
                        continue
                    po = month_stats(runs[ob], YEARS_TRAIN, avail)
                    shifts[ob] = dict(G=round(float(runs[ob].ret.mean()), 3), S=[p['S'] for p in po.values()], GM=[p['GM'] for p in po.values()],
                                      level1=bool(all(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in po.values())))
                d_ok = all(v['level1'] and v['G'] >= 1.0 for v in shifts.values())
                told = campaign(tapes['CNQ'], sig['OLD']['CNQ'], b, T, caches['CNQ'], last=end); pold = month_stats(told, YEARS_TRAIN, avail)
                e_ok = G > float(told.ret.mean())
                key = json.dumps(dict(q=q, target=T, buys=b), sort_keys=True)
                res[key] = dict(n=int(len(t)), G=round(G, 3), WR=round(WR, 1), stops=int((t.reason == 'stop').sum()), worst=round(float(t.ret.min()), 1),
                                S=[p['S'] for p in per.values()], GM=[p['GM'] for p in per.values()], need=[p['need'] for p in per.values()],
                                G_by_year=[p['G'] for p in per.values()], margin=int(margin), excess_vs_every_day_by_year=ex,
                                peers_passed=int(passed), peers_G=round(Gx, 3), peers=xs, entry_shift=shifts,
                                old_information=dict(G=round(float(told.ret.mean()), 3), S=[p['S'] for p in pold.values()], GM=[p['GM'] for p in pold.values()]),
                                break_even_win_rate=round(100 * STOP / (STOP + T), 1),
                                gate=dict(A=bool(a_ok), B=bool(b_ok), C=bool(c_ok), D=bool(d_ok), E=bool(e_ok)), passes=bool(a_ok and b_ok and c_ok and d_ok and e_ok))
                v = res[key]
                print(f"q {q} T {T} {b:18s} | n {v['n']:3d} G {v['G']:5.2f} WR {v['WR']:5.1f} stops {v['stops']:2d} | S {v['S']} GM {v['GM']} need {v['need']} margin {margin:+d} | "
                      f"excess {list(ex.values())} | peers {passed}/18 G {Gx:.2f} | shift {[ (k[:9], x['G'], x['S']) for k, x in shifts.items()]} | old-info G {v['old_information']['G']} S {v['old_information']['S']} | "
                      f"{''.join(k if ok else '-' for k, ok in v['gate'].items())}", flush=True)
    passers = [k for k, v in res.items() if v['passes']]
    out = dict(cutoff=cut, months_available=avail, first_rank_day=str(first_rank.date()), n_settings=len(res), passers=passers,
               gate=__doc__.split('GATE (fixed before the campaign was computed)')[1].split('Family (8 settings)')[0].strip(), settings=res)
    if passers:
        best = max(passers, key=lambda k: (res[k]['margin'], res[k]['peers_passed'], res[k]['G'])); cfg = json.loads(best)
        # final model: all rows whose 20-session label ends by the end of 2023; test years are not in the data
        p14, new = S14.build_panel14(panel, D); feats = L.feature_names(panel) + new
        lastday = cal[-1]; tr = p14.valid & p14[f'fwd{H}'].notna() & p14.vol20.notna() & p14.r60.notna()
        mu = float(p14.loc[tr, f'fwd{H}'].mean()); ms = P.fit_gbm(p14.loc[tr, feats], P.label(p14, H, mu)[tr])
        q = oof[(H, 'NEW')]
        blob = pickle.dumps(dict(chosen={NAME: cfg}, models=ms, feats=feats, mu=mu, train_last=str(p14.loc[tr, 'date'].max().date()),
                                 oof_cnq=q[q.stock == 'CNQ'].set_index('date').pred, gate_passed=True, selection_stats=res[best]))
        open(f'{RES}/{ART}', 'wb').write(blob); out['chosen'] = cfg; out['frozen_sha256'] = hashlib.sha256(blob).hexdigest()
        print('CHOSEN', best, 'trained to', p14.loc[tr, 'date'].max().date(), out['frozen_sha256'][:16], flush=True)
    else:
        print('No setting clears the gate: nothing frozen, no run on 2024-2026.', flush=True)
    json.dump(out, open(f'{RES}/stage14_macro_fusion_selection.json', 'w'), indent=1, default=str)


def blind(verify=False, dry=False):
    logf = f'{RES}/stage13_BLIND_RUN_LOG.json'; resf = f'{RES}/stage13_blind_results.json'
    log = json.load(open(logf)) if os.path.exists(logf) else {}; allres = json.load(open(resf)) if os.path.exists(resf) else {}
    if not dry and (NAME in log) != verify:
        sys.exit('Refused: this model has already had its one run on 2024-2026 (use "verify").' if not verify else 'Nothing to verify yet.')
    assert bool(os.environ.get('S13_CUTOFF')) == dry, 'blind/verify need the full data (unset S13_CUTOFF); dry needs S13_CUTOFF=2023-12-29'
    W0, W1, YRS, MAV = (L.BLIND_START, L.BLIND_END, YEARS_BLIND, MONTHS_BLIND) if not dry else ('2023-01-01', '2023-09-29', [2023], {2023: 9})
    blob = open(f'{RES}/{ART}', 'rb').read(); sha = hashlib.sha256(blob).hexdigest(); fz = pickle.loads(blob); cfg = fz['chosen'][NAME]
    panel, D, intr = P.get_panel(); cal = D['USO'].index
    p14, new = S14.build_panel14(panel, D); assert L.feature_names(panel) + new == fz['feats']
    c = p14[p14.stock == 'CNQ'].set_index('date'); valid = c.valid.to_dict()
    if dry:
        pred = fz['oof_cnq']
    else:
        te = c[(c.index >= L.BLIND_START) & c.valid]
        pred = pd.concat([fz['oof_cnq'], pd.Series(np.mean([m.predict(te[fz['feats']]) for m in fz['models']], axis=0), index=te.index)])
    days, rk = signal_days(pred, valid, cfg['q'])
    tape = Tape(intr['CNQ'], D['CNQ']); cache = {}
    t = campaign(tape, days, cfg['buys'], cfg['target'], cache, first=pd.Timestamp(W0), last=pd.Timestamp(W1))
    per = month_stats(t, YRS, MAV); r = t.ret.values
    rng = np.random.default_rng(0); bs = [rng.choice(r, len(r)).mean() for _ in range(5000)]
    vd = [d for d in tape.days if valid.get(d, False) and pd.Timestamp(W0) <= d <= pd.Timestamp(W1)]
    by = bench_by_year(tape, vd, cfg['buys'], cfg['target'], cache)
    excess = float(np.mean([x - by[y] for x, y in zip(t.ret, t.entry_date.dt.year)]))
    ev = sorted([(a, 1) for a in t.entry_date] + [(b, -1) for b in t.exit_date], key=lambda z: (z[0], -z[1])); cur = mx = 0
    for _, s in ev:
        cur += s; mx = max(mx, cur)
    msum = t.groupby(t.entry_date.dt.strftime('%Y-%m')).ret.sum()
    ic = pred.reindex(c.index).corr(c[f'fwd{H}'], method='spearman') if dry else pred[pred.index >= L.BLIND_START].corr(c[f'fwd{H}'].reindex(pred.index), method='spearman')
    shifts = {}
    for ob in BUYS:
        if ob != cfg['buys']:
            to = campaign(tape, days, ob, cfg['target'], cache, first=pd.Timestamp(W0), last=pd.Timestamp(W1)); po = month_stats(to, YRS, MAV)
            shifts[ob] = dict(G=round(float(to.ret.mean()), 3), WR=round(float((to.ret > 0).mean() * 100), 1), S=[po[y]['S'] for y in YRS], GM=[po[y]['GM'] for y in YRS])
    st = dict(setting=cfg, n=int(len(t)), signals=int(t.signal_day.nunique()), G=round(float(r.mean()), 3), WR=round(float((r > 0).mean() * 100), 1),
              S=[per[y]['S'] for y in YRS], GM=[per[y]['GM'] for y in YRS], per_year=per,
              G_ci95=[round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)], median=round(float(np.median(r)), 3),
              worst_trade=round(float(r.min()), 2), best_trade=round(float(r.max()), 2), exits=t.reason.value_counts().to_dict(),
              net_after_1c=round(float(((t.pnl - 0.01) / t.entry_price * 100).mean()), 3), avg_days_held=round(float(t.days.mean()), 1),
              excess=round(excess, 3), no_skill_line_by_year={int(k): round(float(v), 3) for k, v in by.items()}, max_open_at_once=int(mx),
              worst_month_total_pct=round(float(msum.min()), 1), forecast_rank_ic_20=round(float(ic), 3), entry_shift=shifts)
    payload = json.dumps(st, sort_keys=True, default=str)
    if dry:
        print('DRY RUN on 2023 (nothing written):', {k: st[k] for k in ('n', 'signals', 'G', 'WR', 'S', 'GM', 'exits', 'excess', 'max_open_at_once')}); return
    if verify:
        print('VERIFY', NAME, 'identical' if json.dumps(allres[NAME], sort_keys=True, default=str) == payload else 'DIFFERENT'); return
    allres[NAME] = json.loads(payload)
    log[NAME] = dict(frozen_artefact=ART, frozen_sha256=sha, ran_on=str(pd.Timestamp.now()), blind_window=[L.BLIND_START, L.BLIND_END], blind_look_number=len(log) + 1,
                     result_sha256=hashlib.sha256(payload.encode()).hexdigest(), gate_passed=fz.get('gate_passed', True))
    json.dump(allres, open(resf, 'w'), indent=1); json.dump(log, open(logf, 'w'), indent=1)
    t.insert(0, 'model', NAME)
    t.drop(columns=['entry_price', 'exit_price', 'pnl']).to_csv(f'{RES}/stage14_blind_trades.csv', index=False)
    t.rename(columns={'model': 'method'})[['method', 'entry_date', 'entry_time', 'entry_price', 'pnl']].to_csv(f'{RES}/stage14_blind_trades_LOCAL_ONLY.csv', index=False)
    print(NAME, cfg, {k: st[k] for k in ('n', 'signals', 'G', 'WR', 'S', 'GM', 'G_ci95', 'worst_trade', 'exits', 'excess', 'max_open_at_once', 'worst_month_total_pct', 'forecast_rank_ic_20')}, flush=True)
    print({y: (p['n'], p['G'], p['WR'], p['S'], p['GM'], p['total_pct']) for y, p in per.items()}, 'entry shift:', shifts, flush=True)


if __name__ == '__main__':
    os.makedirs(RES, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    {'select': select, 'dry': lambda: blind(dry=True), 'blind': blind, 'verify': lambda: blind(verify=True)}.get(mode, lambda: print(__doc__))()
