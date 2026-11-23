"""
Stage 13, round 14: model P, a dip-timed monthly campaign.

What the earlier rounds showed (training years only): with model M's exit (+4% target, 15% stop, 60 sessions)
about 83% of ALL entry days end at the target, but the days are not alike. Days after a drop do much better
(lowest fifth of 5-day returns: 93% reach the target, +3.0% per trade; highest fifth: 83%, +0.9%), and the
months that fail are months entered just before a slide (June 2021, June 2022, November 2022, April 2023), in
which only the later, lower days work. Model M buys on the first acceptable day of the month, so it buys
before the slide. Model P waits for a drop.

    signal   each month, the first day (decided at 15:50) on which CNQ has fallen by a set amount; if no such
             day has come by a set trading day of the month, buy anyway on that day (or skip the month)
    buys     two $1,000 buys at different times (owner's same-time rule), or one buy
    exit     target, stop, 60 sessions, each buy on its own
No model is trained: the rule uses CNQ's own prices only, so the same rule can be run unchanged on the five
peer stocks and on late 2020, which the selection does not rank on.

Background: short-term reversal (returns after declines pay for supplying liquidity; Nagel 2012), optimal
entry levels for mean-reverting prices with a stop (Leung and Li 2015), first-passage probabilities for a
target and a stop.

Modes
    select   training years only; needs S13_CUTOFF=2023-12-29 so 2024-2026 is not in the data
    dry      rehearses the blind code on 2023 with the test years removed; writes nothing
    blind    one run on 2024-2026 of the frozen setting; refuses to run twice
    verify   reproduces the stored blind result

GATE (fixed before the search; stricter than rounds 11 to 13 because more settings are tried)
 A. CNQ, each of 2021, 2022, 2023: S >= need + 1 and GM >= need + 1 (need = 8/12 of the months available,
    rounded up); over the three years G >= 1.25% per trade and win rate >= 55%.
 B. The same rule on each of the six stocks: S >= need and GM >= need in at least 15 of 18 stock-years, and at
    least 1.0% per trade across all six.
 C. Late 2020 (September to December, four months, a flat-to-falling start; not used to rank): on CNQ at
    least 3 of 4 months count on S and on GM; across the six stocks at least 16 of 24 stock-months count on both.
 D. Stability: at least half of the setting's neighbours (the next smaller and larger drop size, the next
    earlier and later fallback day; same exit and buys) reach S >= need and GM >= need in every CNQ year.
 Choice among passers: largest worst-year margin on the month goals (CNQ), then stock-years passed in B,
 then neighbours passed, then G. If nothing passes, nothing is frozen and no run on 2024-2026 is made.
"""
import hashlib
import json
import os
import pickle
import sys
import numpy as np
import pandas as pd
import s13_lib as L
from stage13_two_buys import Tape

RES = os.environ.get('S13_OUT', 'results/experiments')
NAME = 'R14_dip_campaign'
ART = 'stage13_frozen_R14.pkl'
HOLD = 60
TRIGGERS = {'r5': [3.0, 4.0, 5.0, 6.0], 'r3': [2.0, 3.0, 4.0], 'dd10': [3.0, 4.0, 5.0, 6.0, 8.0], 'dd20': [4.0, 6.0, 8.0], 'z20': [0.5, 1.0, 1.5]}
FALLBACKS = [5, 10, 15, None]                 # trading day of the month on which to buy anyway; None = skip the month
TARGETS = [3.0, 4.0, 5.5]
STOPS = [10.0, 15.0]
BUYS = {'close+next1000': [(0, 'close'), (1, '10:00')], 'next1000+next1300': [(1, '10:00'), (1, '13:00')], 'close': [(0, 'close')]}
YEARS_TRAIN = [2021, 2022, 2023]
YEARS_BLIND = [2024, 2025, 2026]
MONTHS_BLIND = {2024: 12, 2025: 12, 2026: 11}


def load(symbols):
    intr = {s: L.load_5min(s) for s in symbols}
    D = {s: L.daily(intr[s]) for s in symbols}
    return intr, D


def indicators(d):
    """Causal at 15:50 of each day: drops in percent (positive = fell), and the 20-day z-score."""
    p = np.log(d.p_dec); f = pd.DataFrame(index=d.index)
    f['r5'] = -(p.diff(5)) * 100; f['r3'] = -(p.diff(3)) * 100
    f['dd10'] = -(d.p_dec / d.high.rolling(10).max() - 1) * 100
    f['dd20'] = -(d.p_dec / d.high.rolling(20).max() - 1) * 100
    f['z20'] = -(p - p.rolling(20).mean()) / p.rolling(20).std()
    f['ok'] = d.p_dec.notna() & d.close.notna()
    return f


def signal_days(f, trig, x, fallback):
    """First day of each month on which the drop is at least x; else the fallback trading day; one per month.
    Returns [(day, 'dip' | 'fallback')]."""
    out = []; cur = None; n = 0; done = False
    for d, ok, v in zip(f.index, f.ok.values, f[trig].values):
        m = (d.year, d.month)
        if m != cur:
            cur, n, done = m, 0, False
        if not ok:
            continue
        n += 1
        if done:
            continue
        if not np.isnan(v) and v >= x:
            out.append((d, 'dip')); done = True
        elif fallback is not None and n >= fallback:
            out.append((d, 'fallback')); done = True
    return out


class Sim:
    def __init__(self, sym, intr, D):
        self.tape = Tape(intr[sym], D[sym]); self.f = indicators(D[sym]); self.cache = {}

    def buy(self, d, k, target, stop):
        key = (d, k, target, stop)
        if key not in self.cache:
            self.cache[key] = self.tape.buy(d, k, HOLD, target, stop)
        return self.cache[key]

    def campaign(self, cfg, first=None, last=None):
        t = self.tape; rows = []
        for sd, kind in signal_days(self.f, cfg['trigger'], cfg['x'], cfg['fallback']):
            if sd not in t.pos or (first is not None and sd < first) or (last is not None and sd > last):
                continue
            i = t.pos[sd]; seen = set()
            for off, when in BUYS[cfg['buys']]:
                if i + off >= len(t.days) - 1:
                    continue
                d = t.days[i + off]; k = t.bar_index(d, when)
                if (d, k) in seen:                        # same bar = same time = one trade (owner's rule)
                    continue
                seen.add((d, k))
                entry, xd, px, why = self.buy(d, k, cfg['target'], cfg['stop'])
                mins = t.bars[d][0][k] + 5
                rows.append(dict(signal_day=sd, kind=kind, entry_date=d, entry_time=f'{mins // 60:02d}:{mins % 60:02d}', exit_date=xd, side=1,
                                 entry_price=entry, exit_price=px, pnl=px - entry, ret=(px / entry - 1) * 100, reason=why, days=t.pos[xd] - t.pos[d]))
        cols = ['signal_day', 'kind', 'entry_date', 'entry_time', 'exit_date', 'side', 'entry_price', 'exit_price', 'pnl', 'ret', 'reason', 'days']
        return pd.DataFrame(rows, columns=cols)


def month_stats(t, years, months_avail, months_list=None):
    per = {}
    for y in years:
        ty = t[t.entry_date.dt.year == y]
        if months_list is not None:
            ty = ty[ty.entry_date.dt.month.isin(months_list)]
        g = ty.groupby(ty.entry_date.dt.month).ret; avail = months_avail[y]
        both = int(((g.mean() > 1) & (g.sum() >= 5)).sum())
        per[y] = dict(n=int(len(ty)), G=round(float(ty.ret.mean()), 3) if len(ty) else None, WR=round(float((ty.ret > 0).mean() * 100), 1) if len(ty) else None,
                      S=int((g.mean() > 1).sum()), GM=int((g.sum() >= 5).sum()), both=both, months=avail, need=int(np.ceil(8 / 12 * avail)),
                      total_pct=round(float(ty.ret.sum()), 1))
    return per


def key_of(cfg):
    return json.dumps(cfg, sort_keys=True)


def neighbours(cfg):
    out = []; xs = TRIGGERS[cfg['trigger']]; i = xs.index(cfg['x']); j = FALLBACKS.index(cfg['fallback'])
    for ii in (i - 1, i + 1):
        if 0 <= ii < len(xs):
            out.append(dict(cfg, x=xs[ii]))
    for jj in (j - 1, j + 1):
        if 0 <= jj < len(FALLBACKS):
            out.append(dict(cfg, fallback=FALLBACKS[jj]))
    return out


def select():
    cut = os.environ.get('S13_CUTOFF', '')
    assert cut and cut <= '2023-12-31', 'run the selection with S13_CUTOFF=2023-12-29'
    intr, D = load(L.STOCKS)
    assert max(d.index.max() for d in D.values()) <= pd.Timestamp('2023-12-31')
    sims = {s: Sim(s, intr, D) for s in L.STOCKS}
    end = sims['CNQ'].tape.days[-HOLD - 2]
    avail = {2021: 12, 2022: 12, 2023: int(end.month)}
    res = {}
    grid = [dict(trigger=tr, x=x, fallback=fb, target=T, stop=st, buys=b) for tr, xs in TRIGGERS.items() for x in xs for fb in FALLBACKS
            for T in TARGETS for st in STOPS for b in BUYS if not (b == 'close' and T < 5.5)]
    for n, cfg in enumerate(grid):
        t = sims['CNQ'].campaign(cfg, last=end); tt = t[t.entry_date.dt.year.isin(YEARS_TRAIN)]
        per = month_stats(tt, YEARS_TRAIN, avail)
        if len(tt) == 0:
            continue
        G = float(tt.ret.mean()); WR = float((tt.ret > 0).mean() * 100)
        margin = min(min(p['S'], p['GM']) - p['need'] for p in per.values())
        level1 = all(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in per.values())
        a_ok = margin >= 1 and G >= 1.25 and WR >= 55
        passed = 0; allr = []; stress_months = 0
        for s in L.STOCKS:
            ts = sims[s].campaign(cfg, last=end)
            ps = month_stats(ts[ts.entry_date.dt.year.isin(YEARS_TRAIN)], YEARS_TRAIN, avail); allr.append(ts[ts.entry_date.dt.year.isin(YEARS_TRAIN)].ret)
            passed += sum(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in ps.values())
            stress_months += month_stats(ts, [2020], {2020: 4}, months_list=[9, 10, 11, 12])[2020]['both']
        Gx = float(pd.concat(allr).mean()); b_ok = passed >= 15 and Gx >= 1.0
        st20 = month_stats(t, [2020], {2020: 4}, months_list=[9, 10, 11, 12])[2020]
        c_ok = st20['S'] >= 3 and st20['GM'] >= 3 and stress_months >= 16
        res[key_of(cfg)] = dict(n=int(len(tt)), G=round(G, 3), WR=round(WR, 1), worst=round(float(tt.ret.min()), 1), stops=int((tt.reason == 'stop').sum()),
                                dips=int((tt.kind == 'dip').sum()), fallbacks=int((tt.kind == 'fallback').sum()),
                                S=[p['S'] for p in per.values()], GM=[p['GM'] for p in per.values()], need=[p['need'] for p in per.values()],
                                G_by_year=[p['G'] for p in per.values()], margin=int(margin), level1=bool(level1), cross_passed=int(passed), cross_G=round(Gx, 3),
                                stress2020=dict(cnq_S=st20['S'], cnq_GM=st20['GM'], cnq_G=st20['G'], cnq_n=st20['n'], six_stock_months=int(stress_months)),
                                gate_A=bool(a_ok), gate_B=bool(b_ok), gate_C=bool(c_ok))
        if n % 100 == 0:
            print('..', n, 'of', len(grid), flush=True)
    for k, v in res.items():
        nb = [res.get(key_of(c)) for c in neighbours(json.loads(k))]; nb = [x for x in nb if x is not None]
        v['neighbours'] = len(nb); v['neighbours_level1'] = int(sum(x['level1'] for x in nb))
        v['gate_D'] = bool(nb and v['neighbours_level1'] * 2 >= len(nb))
        v['passes'] = bool(v['gate_A'] and v['gate_B'] and v['gate_C'] and v['gate_D'])
    rank = lambda k: (res[k]['margin'], res[k]['cross_passed'], res[k]['neighbours_level1'], res[k]['G'])
    print('\ntrigger  x  fallback target stop buys              |  n    G    WR  worst stops dip/fb | S | GM | need | margin | cross G | 2020: S GM six | nb | A B C D', flush=True)
    for k in sorted(res, key=rank, reverse=True)[:30]:
        c = json.loads(k); v = res[k]
        print(f"{c['trigger']:5s} {c['x']:4.1f} {str(c['fallback']):>5s} {c['target']:5.1f} {c['stop']:4.0f} {c['buys']:18s} | {v['n']:3d} {v['G']:5.2f} {v['WR']:5.1f} {v['worst']:6.1f} {v['stops']:3d} "
              f"{v['dips']:3d}/{v['fallbacks']:<3d} | {v['S']} | {v['GM']} | {v['need']} | {v['margin']:+d} | {v['cross_passed']:2d} {v['cross_G']:5.2f} | "
              f"{v['stress2020']['cnq_S']} {v['stress2020']['cnq_GM']} {v['stress2020']['six_stock_months']:2d} | {v['neighbours_level1']}/{v['neighbours']} | "
              f"{'A' if v['gate_A'] else '-'} {'B' if v['gate_B'] else '-'} {'C' if v['gate_C'] else '-'} {'D' if v['gate_D'] else '-'}", flush=True)
    passers = [k for k, v in res.items() if v['passes']]
    out = dict(cutoff=cut, data_last_day=str(max(d.index.max() for d in D.values()).date()), n_settings=len(res),
               counts=dict(gate_A=sum(v['gate_A'] for v in res.values()), gate_B=sum(v['gate_B'] for v in res.values()), gate_C=sum(v['gate_C'] for v in res.values()),
                           gate_D=sum(v['gate_D'] for v in res.values()), level1=sum(v['level1'] for v in res.values()), passers=len(passers)),
               gate=__doc__.split('GATE (fixed before the search')[1].strip(), passers=sorted(passers, key=rank, reverse=True), settings=res)
    print('settings', len(res), out['counts'], flush=True)
    if passers:
        best = max(passers, key=rank); cfg = json.loads(best)
        blob = pickle.dumps(dict(chosen={NAME: cfg}, hold=HOLD, selection_stats=res[best]))
        open(f'{RES}/{ART}', 'wb').write(blob); out['chosen'] = cfg; out['chosen_stats'] = res[best]; out['frozen_sha256'] = hashlib.sha256(blob).hexdigest()
        print('CHOSEN', best, res[best], out['frozen_sha256'][:16], flush=True)
    else:
        print('No setting clears the gate: nothing frozen, no run on 2024-2026.', flush=True)
    json.dump(out, open(f'{RES}/stage13_round14_dip_campaign_selection.json', 'w'), indent=1, default=str)


def blind(verify=False, dry=False):
    logf = f'{RES}/stage13_BLIND_RUN_LOG.json'; resf = f'{RES}/stage13_blind_results.json'
    log = json.load(open(logf)) if os.path.exists(logf) else {}
    allres = json.load(open(resf)) if os.path.exists(resf) else {}
    if not dry and (NAME in log) != verify:
        sys.exit('Refused: this model has already had its one run on 2024-2026 (use "verify").' if not verify else 'Nothing to verify yet.')
    assert bool(os.environ.get('S13_CUTOFF')) == dry, 'blind/verify need the full data (unset S13_CUTOFF); dry needs S13_CUTOFF=2023-12-29'
    W0, W1, YRS, MAV = (L.BLIND_START, L.BLIND_END, YEARS_BLIND, MONTHS_BLIND) if not dry else ('2023-01-01', '2023-09-29', [2023], {2023: 9})
    blob = open(f'{RES}/{ART}', 'rb').read(); sha = hashlib.sha256(blob).hexdigest(); frozen = pickle.loads(blob)
    cfg = frozen['chosen'][NAME]
    intr, D = load(['CNQ']); sim = Sim('CNQ', intr, D)
    t = sim.campaign(cfg, first=pd.Timestamp(W0), last=pd.Timestamp(W1))
    per = month_stats(t, YRS, MAV); r = t.ret.values
    rng = np.random.default_rng(0); bs = [rng.choice(r, len(r)).mean() for _ in range(5000)]
    # no-skill line: the same buys and the same exit after EVERY day
    rows = []; tp = sim.tape
    for d in [x for x in tp.days if pd.Timestamp(W0) <= x <= pd.Timestamp(W1)]:
        i = tp.pos[d]
        for off, when in BUYS[cfg['buys']]:
            if i + off < len(tp.days) - 1:
                dd = tp.days[i + off]; e, xd, px, why = sim.buy(dd, tp.bar_index(dd, when), cfg['target'], cfg['stop']); rows.append((dd.year, (px / e - 1) * 100))
    by = pd.DataFrame(rows, columns=['y', 'ret']).groupby('y').ret.mean()
    excess = float(np.mean([x - by[y] for x, y in zip(t.ret, t.entry_date.dt.year)]))
    ev = sorted([(a, 1) for a in t.entry_date] + [(b, -1) for b in t.exit_date], key=lambda z: (z[0], -z[1])); cur = mx = 0
    for _, s in ev:
        cur += s; mx = max(mx, cur)
    msum = t.groupby(t.entry_date.dt.strftime('%Y-%m')).ret.sum()
    st = dict(setting=cfg, n=int(len(t)), signals=int(t.signal_day.nunique()), dip_signals=int(t[t.kind == 'dip'].signal_day.nunique()),
              fallback_signals=int(t[t.kind == 'fallback'].signal_day.nunique()), G=round(float(r.mean()), 3), WR=round(float((r > 0).mean() * 100), 1),
              S=[per[y]['S'] for y in YRS], GM=[per[y]['GM'] for y in YRS], per_year=per,
              G_ci95=[round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)], median=round(float(np.median(r)), 3),
              worst_trade=round(float(r.min()), 2), best_trade=round(float(r.max()), 2), exits=t.reason.value_counts().to_dict(),
              G_dip=round(float(t[t.kind == 'dip'].ret.mean()), 3) if (t.kind == 'dip').any() else None,
              G_fallback=round(float(t[t.kind == 'fallback'].ret.mean()), 3) if (t.kind == 'fallback').any() else None,
              net_after_1c=round(float(((t.pnl - 0.01) / t.entry_price * 100).mean()), 3), avg_days_held=round(float(t.days.mean()), 1),
              excess=round(excess, 3), no_skill_line_by_year={int(k): round(float(v), 3) for k, v in by.items()}, max_open_at_once=int(mx),
              worst_month_total_pct=round(float(msum.min()), 1), best_month_total_pct=round(float(msum.max()), 1))
    payload = json.dumps(st, sort_keys=True, default=str)
    if dry:
        print('DRY RUN on 2023 (nothing written):', {k: st[k] for k in ('n', 'signals', 'dip_signals', 'fallback_signals', 'G', 'WR', 'S', 'GM', 'exits', 'excess', 'max_open_at_once')}); return
    if verify:
        print('VERIFY', NAME, 'identical' if json.dumps(allres[NAME], sort_keys=True, default=str) == payload else 'DIFFERENT'); return
    allres[NAME] = json.loads(payload)
    log[NAME] = dict(frozen_artefact=ART, frozen_sha256=sha, ran_on=str(pd.Timestamp.now()), blind_window=[L.BLIND_START, L.BLIND_END],
                     blind_look_number=len(log) + 1, result_sha256=hashlib.sha256(payload.encode()).hexdigest())
    json.dump(allres, open(resf, 'w'), indent=1); json.dump(log, open(logf, 'w'), indent=1)
    t.insert(0, 'model', NAME)
    t.drop(columns=['entry_price', 'exit_price', 'pnl']).to_csv(f'{RES}/stage13_round14_blind_trades.csv', index=False)          # published: no prices
    t.rename(columns={'model': 'method'})[['method', 'entry_date', 'entry_time', 'entry_price', 'pnl']].to_csv(
        f'{RES}/stage13_round14_blind_trades_LOCAL_ONLY.csv', index=False)
    print(NAME, cfg, {k: st[k] for k in ('n', 'signals', 'dip_signals', 'fallback_signals', 'G', 'WR', 'S', 'GM', 'G_ci95', 'worst_trade', 'exits', 'excess',
                                         'G_dip', 'G_fallback', 'max_open_at_once', 'worst_month_total_pct')}, flush=True)
    print({y: (p['n'], p['G'], p['WR'], p['S'], p['GM'], p['total_pct']) for y, p in per.items()}, flush=True)


if __name__ == '__main__':
    os.makedirs(RES, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'select':
        select()
    elif mode == 'dry':
        blind(dry=True)
    elif mode == 'blind':
        blind()
    elif mode == 'verify':
        blind(verify=True)
    else:
        print(__doc__)
