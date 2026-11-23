"""
Stage 13, round 15 search (training years only): model Q, a monthly campaign whose DIRECTION follows the trend.

Why: models M, O and P lose their months and their profit in slides, when a long campaign is stopped out. The
best-documented way to take the other side of a slide is time-series momentum (Moskowitz, Ooi and Pedersen
2012): go with the sign of the asset's own past return. Model Q is model O's campaign (two buys at 10:00 and
13:00 of the session after the month's first trading day; target, 15% stop, 60 sessions) taken LONG when the
trend is up and SHORT when it is down.

Run with S13_CUTOFF=2023-12-29 so that 2024-2026 is not in the data. Nothing here touches the test years.

Family: trend source own stock | sector fund (XLE) | six-stock basket;  lookback 20, 40, 60, 120 sessions;
        target 3 or 4%.  24 settings, plus "always long" with the same exit as the no-skill line.

GATE (fixed before the search; P's gate plus the two checks added after P)
 A. CNQ, each of 2021, 2022, 2023: S >= need + 1 and GM >= need + 1; G >= 1.25% and win rate >= 55% overall.
 B. Same rule on the six stocks: level 1 on both month goals in at least 15 of 18 stock-years, and >= 1.0% per trade.
 C. September to December 2020: CNQ at least 3 of 4 months on S and GM; six stocks at least 16 of 24 stock-months.
 D. At least half of the neighbouring settings (next shorter and longer lookback, the other target) reach level 1
    in every CNQ year.
 E. The direction rule must not do worse than "always long, same exit" in any CNQ training year, and must do
    better over the three years together.
 F. (reported, not pass/fail) break-even win rate of the exit against the training win rate.
 If nothing passes A to E, nothing is frozen and no run on 2024-2026 is made.
"""
import json, os, sys
import numpy as np, pandas as pd
import s13_lib as L
from stage13_two_buys import Tape

RES = os.environ.get('S13_OUT', 'results/experiments')
HOLD, STOP = 60, 15.0
SOURCES = ['own', 'xle', 'basket']; LOOKS = [20, 40, 60, 120]; TARGETS = [3.0, 4.0]
YEARS = [2021, 2022, 2023]


def trade(tape, day, k, side, target):
    i = tape.pos[day]; entry = float(tape.bars[day][4][k])
    tp = entry * (1 + side * target / 100); sl = entry * (1 - side * STOP / 100)
    last = min(i + HOLD, len(tape.days) - 1)
    for j in range(i, last + 1):
        d = tape.days[j]; mins, o, h, l, c = tape.bars[d]
        for b in range(k + 1 if j == i else 0, len(o)):
            if (l[b] <= sl) if side > 0 else (h[b] >= sl):
                px = min(o[b], sl) if side > 0 else max(o[b], sl); return side * (px / entry - 1) * 100, 'stop'
            if (h[b] >= tp) if side > 0 else (l[b] <= tp):
                px = max(o[b], tp) if side > 0 else min(o[b], tp); return side * (px / entry - 1) * 100, 'target'
    d = tape.days[last]
    return side * (float(tape.bars[d][4][-1]) / entry - 1) * 100, 'time'


def main():
    cut = os.environ.get('S13_CUTOFF', ''); assert cut and cut <= '2023-12-31'
    syms = L.STOCKS + ['XLE']
    intr = {s: L.load_5min(s) for s in syms}; D = {s: L.daily(intr[s]) for s in syms}
    cal = D['XLE'].index; assert cal.max() <= pd.Timestamp('2023-12-31')
    lp = pd.DataFrame({s: np.log(D[s].p_dec.reindex(cal)) for s in syms})
    tapes = {s: Tape(intr[s], D[s]) for s in L.STOCKS}
    end = tapes['CNQ'].days[-HOLD - 2]; avail = {2020: 4, 2021: 12, 2022: 12, 2023: int(end.month)}
    cache = {}

    def campaign(s, source, look, target):
        t = tapes[s]; rows = []; seen = set()
        tr = {'own': lp[s], 'xle': lp['XLE'], 'basket': lp[L.STOCKS].mean(axis=1)}.get(source)
        for d in t.days:
            m = (d.year, d.month)
            if m in seen or d > end:
                continue
            seen.add(m)                                           # first trading day of the month, decided at 15:50
            if source == 'long':
                side = 1
            else:
                v = tr.diff(look).get(d, np.nan)
                if np.isnan(v):
                    continue
                side = 1 if v >= 0 else -1
            i = t.pos[d]
            if i + 1 >= len(t.days) - 1:
                continue
            nd = t.days[i + 1]
            for when in ('10:00', '13:00'):
                k = t.bar_index(nd, when); key = (s, nd, k, side, target)
                if key not in cache:
                    cache[key] = trade(t, nd, k, side, target)
                r, why = cache[key]; rows.append((nd.year, nd.month, side, r, why))
        return pd.DataFrame(rows, columns=['y', 'm', 'side', 'ret', 'why'])

    def stats(t, years):
        per = {}
        for y in years:
            ty = t[t.y == y] if y != 2020 else t[(t.y == 2020) & (t.m >= 9)]
            g = ty.groupby('m').ret; need = int(np.ceil(8 / 12 * avail[y]))
            per[y] = dict(n=int(len(ty)), G=float(ty.ret.mean()) if len(ty) else np.nan, S=int((g.mean() > 1).sum()), GM=int((g.sum() >= 5).sum()),
                          both=int(((g.mean() > 1) & (g.sum() >= 5)).sum()), need=need, shorts=int((ty.side < 0).sum()))
        return per

    base = {T: stats(campaign('CNQ', 'long', 0, T), YEARS) for T in TARGETS}
    res = {}
    for src in SOURCES + ['long']:
        for look in (LOOKS if src != 'long' else [0]):
            for T in TARGETS:
                t = campaign('CNQ', src, look, T); tt = t[t.y.isin(YEARS)]; per = stats(t, YEARS)
                G = float(tt.ret.mean()); WR = float((tt.ret > 0).mean() * 100)
                margin = min(min(p['S'], p['GM']) - p['need'] for p in per.values())
                level1 = all(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in per.values())
                passed = 0; allr = []; stress = 0
                for s in L.STOCKS:
                    ts = campaign(s, src, look, T); ps = stats(ts, YEARS); allr.append(ts[ts.y.isin(YEARS)].ret)
                    passed += sum(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in ps.values()); stress += stats(ts, [2020])[2020]['both']
                s20 = stats(t, [2020])[2020]; Gx = float(pd.concat(allr).mean())
                ex = [per[y]['G'] - base[T][y]['G'] for y in YEARS]; ex_all = G - float(np.nanmean([0]))  # placeholder, replaced below
                bt = campaign('CNQ', 'long', 0, T); ex_all = G - float(bt[bt.y.isin(YEARS)].ret.mean())
                res[json.dumps(dict(source=src, look=look, target=T))] = dict(
                    n=int(len(tt)), shorts=int((tt.side < 0).sum()), G=round(G, 3), WR=round(WR, 1), stops=int((tt.why == 'stop').sum()),
                    S=[p['S'] for p in per.values()], GM=[p['GM'] for p in per.values()], need=[p['need'] for p in per.values()],
                    G_by_year=[round(p['G'], 2) for p in per.values()], excess_vs_always_long_by_year=[round(x, 2) for x in ex], excess_overall=round(ex_all, 3),
                    margin=int(margin), level1=bool(level1), cross_passed=int(passed), cross_G=round(Gx, 3),
                    stress2020=dict(S=s20['S'], GM=s20['GM'], six=int(stress)), break_even_win_rate=round(100 * STOP / (STOP + T), 1),
                    gate_A=bool(margin >= 1 and G >= 1.25 and WR >= 55), gate_B=bool(passed >= 15 and Gx >= 1.0),
                    gate_C=bool(s20['S'] >= 3 and s20['GM'] >= 3 and stress >= 16), gate_E=bool(src != 'long' and min(ex) >= 0 and ex_all > 0))
    for k, v in res.items():
        c = json.loads(k); nb = []
        if c['source'] != 'long':
            i = LOOKS.index(c['look'])
            nb += [json.dumps(dict(c, look=LOOKS[j])) for j in (i - 1, i + 1) if 0 <= j < len(LOOKS)]
            nb += [json.dumps(dict(c, target=[x for x in TARGETS if x != c['target']][0]))]
        v['neighbours_level1'] = int(sum(res[n]['level1'] for n in nb)); v['neighbours'] = len(nb)
        v['gate_D'] = bool(nb and v['neighbours_level1'] * 2 >= len(nb))
        v['passes'] = bool(v['gate_A'] and v['gate_B'] and v['gate_C'] and v['gate_D'] and v['gate_E'])
    print('source look target |  n shorts    G    WR stops | S | GM | need | margin | cross G | 2020 S GM six | G by year | excess vs always long by year, all | BE win% | A B C D E')
    for k, v in res.items():
        c = json.loads(k)
        print(f"{c['source']:6s} {c['look']:4d} {c['target']:4.1f} | {v['n']:3d} {v['shorts']:4d} {v['G']:6.2f} {v['WR']:5.1f} {v['stops']:3d} | {v['S']} | {v['GM']} | {v['need']} | {v['margin']:+d} | "
              f"{v['cross_passed']:2d} {v['cross_G']:5.2f} | {v['stress2020']['S']} {v['stress2020']['GM']} {v['stress2020']['six']:2d} | {v['G_by_year']} | {v['excess_vs_always_long_by_year']} {v['excess_overall']:+.2f} | "
              f"{v['break_even_win_rate']} | {'A' if v['gate_A'] else '-'} {'B' if v['gate_B'] else '-'} {'C' if v['gate_C'] else '-'} {'D' if v['gate_D'] else '-'} {'E' if v['gate_E'] else '-'}", flush=True)
    passers = [k for k, v in res.items() if v['passes']]
    json.dump(dict(cutoff=cut, n_settings=len(res) - len(TARGETS), passers=passers, gate=__doc__.split('GATE (fixed before the search')[1].strip(), settings=res),
              open(f'{RES}/stage13_round15_trend_direction_search.json', 'w'), indent=1)
    print('passers', len(passers), 'of', len(res) - len(TARGETS), passers)


if __name__ == '__main__':
    main()
