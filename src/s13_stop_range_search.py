"""
Stage 13, round 12 search (training years only): the owner asked that the next model consider stops anywhere
from 1% to 15%. This repeats the round 11 search with ten stop sizes, a wider set of targets and time limits,
and one more way of using a tight stop: trying again after being stopped out.

Run with S13_CUTOFF=2023-12-29 so that 2024-2026 is not in the data at all. Nothing here touches the test years.

GATE: unchanged from round 11 (src/s13_ladder_gate_search.py), fixed before this search was run.
 A. CNQ, model entry, each of 2021, 2022, 2023: S >= need + 1 and GM >= need + 1; over the three years
    G >= 1.25% per trade and win rate >= 55%.
 B. Same rule, calendar entry, six stocks: S >= need and GM >= need in at least 14 of 18 stock-years, and at
    least 1.0% per trade across all six.
 C. Two trades opened on the same day are reported but not eligible.
 Choice among passers: largest worst-year margin on the month goals, then stock-years passed, then G.
 If nothing passes, nothing is frozen and no run on 2024-2026 is made.

Family:
   stop     1, 2, 3, 4, 5, 6, 8, 10, 12, 15 %
   target   2.6, 3, 4, 5.5, 7, 9 %
   limit    20, 40, 60 sessions
   second entry: none | same | lag5 | lag10 | dip2 | dip3 | up1 | up2 | retry2 | retry3
        retryK = after a trade is stopped out, buy again at that day's close, at most K trades in the month
"""
import json
import os
import pickle
import numpy as np
import pandas as pd
import s13_lib as L
import stage13_peer_fusion as P
from s13_ladder_gate_search import first_entries, second_entry, YEARS

RES = os.environ.get('S13_OUT', 'results/experiments')
STOPS = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0]
TARGETS = [2.6, 3.0, 4.0, 5.5, 7.0, 9.0]
HOLDS = [20, 40, 60]
SECOND = ['none', 'same', 'lag5', 'lag10', 'dip2', 'dip3', 'up1', 'up2', 'retry2', 'retry3']


class Sim:
    def __init__(self, sym, intr, D):
        self.path = L.Path(intr[sym], D[sym]); self.close = D[sym].close
        self.days = self.path.days
        self.by_month = {}
        for d in self.days:
            self.by_month.setdefault((d.year, d.month), []).append(d)
        self.cache = {}

    def ret(self, d, hold, target, stop):
        k = (d, hold, target, stop)
        if k not in self.cache:
            xd, px, why = self.path.trade(d, 1, hold, target, stop)
            self.cache[k] = ((px / float(self.close[d]) - 1) * 100, why, xd)
        return self.cache[k]

    def campaign(self, firsts, rule, hold, target, stop):
        end = self.days[-hold - 1]; rows = []
        for m, d1 in firsts.items():
            if d1 > end or d1.year not in YEARS:
                continue
            if rule.startswith('retry'):
                k = int(rule[-1]); d = d1; n = 0
                while d is not None and n < k and d <= end and (d.year, d.month) == m:
                    r, why, xd = self.ret(d, hold, target, stop); rows.append((m[0], m[1], r, why)); n += 1
                    d = xd if why == 'stop' else None          # stopped out: buy again at that day's close
            else:
                ds = [d1]; d2 = second_entry(rule, d1, self.by_month[m], self.close)
                if d2 is not None and d2 <= end:
                    ds.append(d2)
                for d in ds:
                    r, why, _ = self.ret(d, hold, target, stop); rows.append((m[0], m[1], r, why))
        t = pd.DataFrame(rows, columns=['y', 'm', 'ret', 'why'])
        per = {}
        for y in YEARS:
            ty = t[t.y == y]; avail = 12 if y < YEARS[-1] else int(end.month); g = ty.groupby('m').ret
            need = int(np.ceil(8 / 12 * avail))
            per[y] = dict(n=int(len(ty)), G=round(float(ty.ret.mean()), 3) if len(ty) else None, S=int((g.mean() > 1).sum()),
                          GM=int((g.sum() >= 5).sum()), months=avail, need=need)
        return t, per


def main():
    cut = os.environ.get('S13_CUTOFF', '')
    assert cut and cut <= '2023-12-31', 'run with S13_CUTOFF=2023-12-29'
    panel, D, intr = P.get_panel()
    cal = D['USO'].index
    assert cal.max() <= pd.Timestamp('2023-12-31')
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    score = P.score_series(frozen['oof'][5], 'gbm')
    sims = {s: Sim(s, intr, D) for s in L.STOCKS}
    valid = {s: panel[panel.stock == s].set_index('date').valid.to_dict() for s in L.STOCKS}
    f_ml = first_entries(sims['CNQ'].days, valid['CNQ'], score.to_dict())
    f_cal = {s: first_entries(sims[s].days, valid[s]) for s in L.STOCKS}
    res = {}
    for st in STOPS:
        for rule in SECOND:
            for T in TARGETS:
                for H in HOLDS:
                    t, per = sims['CNQ'].campaign(f_ml, rule, H, T, st)
                    G = float(t.ret.mean()); WR = float((t.ret > 0).mean() * 100)
                    margin = min(min(p['S'], p['GM']) - p['need'] for p in per.values())
                    a_ok = margin >= 1 and G >= 1.25 and WR >= 55
                    passed = 0; allr = []
                    for s in L.STOCKS:
                        ts, ps = sims[s].campaign(f_cal[s], rule, H, T, st); allr.append(ts.ret)
                        passed += sum(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in ps.values())
                    Gx = float(pd.concat(allr).mean()); b_ok = passed >= 14 and Gx >= 1.0
                    key = json.dumps(dict(second=rule, target=T, stop=st, hold=H), sort_keys=True)
                    res[key] = dict(n=int(len(t)), G=round(G, 3), WR=round(WR, 1), worst=round(float(t.ret.min()), 1), stops=int((t.why == 'stop').sum()),
                                    S=[p['S'] for p in per.values()], GM=[p['GM'] for p in per.values()], need=[p['need'] for p in per.values()],
                                    G_by_year=[p['G'] for p in per.values()], margin=int(margin), cross_passed=int(passed), cross_G=round(Gx, 3),
                                    gate_A=bool(a_ok), gate_B=bool(b_ok), eligible=rule != 'same', passes=bool(a_ok and b_ok and rule != 'same'))
        print('stop', st, 'done', flush=True)
    by_stop = {}
    print('\nBest eligible setting at each stop size (by worst-year margin on the month goals, then G):', flush=True)
    print('stop | second target hold |  n     G    WR  worst stops | S | GM | need | margin | cross x/18  G | gates', flush=True)
    for st in STOPS:
        el = {k: v for k, v in res.items() if v['eligible'] and json.loads(k)['stop'] == st}
        k = max(el, key=lambda k: (el[k]['margin'], el[k]['G'])); v = el[k]; c = json.loads(k)
        by_stop[str(st)] = dict(best=c, stats=v, n_settings=len(el), gate_A=sum(x['gate_A'] for x in el.values()), gate_B=sum(x['gate_B'] for x in el.values()),
                                passers=sum(x['passes'] for x in el.values()),
                                best_G_with_WR50=max([x['G'] for x in el.values() if x['WR'] >= 50] or [None]),
                                share_with_WR50=round(float(np.mean([x['WR'] >= 50 for x in el.values()])), 2))
        print(f"{st:4.0f} | {c['second']:6s} {c['target']:4.1f} {c['hold']:3d} | {v['n']:3d} {v['G']:6.2f} {v['WR']:5.1f} {v['worst']:6.1f} {v['stops']:3d} | {v['S']} | {v['GM']} | {v['need']} | "
              f"{v['margin']:+d} | {v['cross_passed']:2d} {v['cross_G']:5.2f} | A:{by_stop[str(st)]['gate_A']} B:{by_stop[str(st)]['gate_B']} pass:{by_stop[str(st)]['passers']}", flush=True)
    passers = {k: v for k, v in res.items() if v['passes']}
    same = sorted(k for k, v in res.items() if not v['eligible'] and v['gate_A'] and v['gate_B'])
    out = dict(cutoff=cut, data_last_day=str(cal.max().date()), n_settings=len(res), n_eligible=sum(v['eligible'] for v in res.values()),
               passers=sorted(passers), same_day_settings_that_would_pass=same, by_stop=by_stop, settings=res)
    if passers:
        best = max(passers, key=lambda k: (passers[k]['margin'], passers[k]['cross_passed'], passers[k]['G']))
        out['chosen'] = json.loads(best); out['chosen_stats'] = passers[best]; print('CHOSEN', best, flush=True)
    json.dump(out, open(f'{RES}/stage13_round12_stop_range_search.json', 'w'), indent=1, default=str)
    print('eligible passers', len(passers), 'of', out['n_eligible'], '| same-day settings clearing A and B:', same, flush=True)


if __name__ == '__main__':
    main()
