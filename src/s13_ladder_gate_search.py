"""
Stage 13, round 11 search (training years only): can a monthly campaign with a second entry reach level 1 on
all four goals WITH A MARGIN, and does the same rule hold on the five peer stocks?

Run with S13_CUTOFF=2023-12-29 so that 2024-2026 is not in the data at all. Nothing here touches the test years.

Why this search exists. Model N passed its training gate exactly at the threshold and then failed on 2024-2026.
Two changes to the gate, written down here before anything is computed:

GATE (pre-registered)
 A. CNQ with the entry the model would use on the test years (first day of the month on which the Peer-Fusion
    model's trailing rank is at least 0.5), in EACH of 2021, 2022, 2023:
        S  >= need + 1   and   GM >= need + 1      (need = 8/12 of the months available, rounded up)
    and over the three years together: G >= 1.25% per trade, win rate >= 55%.
 B. The same exit and the same second-entry rule on each of the six stocks with a plain calendar entry (first
    trading day of the month; no model): at least 14 of the 18 stock-years reach S >= need and GM >= need,
    and the average over all six stocks' trades is at least 1.0% per trade.
 C. The second entry is a separate decision on a later day. Two $1,000 trades opened on the same day at the
    same price are one $2,000 position; that variant is computed and reported ("same") but is NOT eligible,
    because whether it should count towards GM is the owner's decision, not a modelling result.
 Choice among passers: the largest worst-year margin on the two month goals (CNQ), then the number of
 stock-years passed in B, then G. If nothing passes, nothing is frozen and no run on 2024-2026 is made.

Family searched (all long, every trade carries a stop, trades may overlap, results counted by entry month):
   second entry: none | same | lag5 | lag10 | dip2 | dip3 | up1 | up2
        lagN = first trading day at least N sessions after the first entry, same calendar month
        dipX = first later day of the month whose close is X% or more below the first entry
        upX  = first later day of the month whose close is X% or more above the first entry
   target 2.6, 3, 4, 5.5 %   stop 10, 15 %   time limit 40, 60 sessions
"""
import json
import os
import pickle
import sys
import numpy as np
import pandas as pd
import s13_lib as L
import stage13_peer_fusion as P

RES = os.environ.get('S13_OUT', 'results/experiments')
YEARS = [2021, 2022, 2023]
SECOND = ['none', 'same', 'lag5', 'lag10', 'dip2', 'dip3', 'up1', 'up2']
TARGETS = [2.6, 3.0, 4.0, 5.5]
STOPS = [10.0, 15.0]
HOLDS = [40, 60]


def first_entries(days, valid, score=None, q=0.5):
    """One first entry per calendar month: first valid day (calendar) or first day the score clears q (model)."""
    out = {}
    for d in days:
        if not valid.get(d, False):
            continue
        m = (d.year, d.month)
        if m in out:
            continue
        if score is None or (not np.isnan(score.get(d, np.nan)) and score[d] >= q):
            out[m] = d
    return out


def second_entry(rule, d1, month_days, close):
    later = [d for d in month_days if d > d1]
    if rule == 'none':
        return None
    if rule == 'same':
        return d1
    if rule.startswith('lag'):
        n = int(rule[3:]); i = month_days.index(d1)
        return month_days[i + n] if i + n < len(month_days) else None
    x = float(rule[-1]); e = close[d1]
    for d in later:
        if rule.startswith('dip') and close[d] <= e * (1 - x / 100):
            return d
        if rule.startswith('up') and close[d] >= e * (1 + x / 100):
            return d
    return None


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
            self.cache[k] = ((px / float(self.close[d]) - 1) * 100, why)
        return self.cache[k]

    def campaign(self, firsts, rule, hold, target, stop):
        end = self.days[-hold - 1]; rows = []
        for m, d1 in firsts.items():
            if d1 > end or d1.year not in YEARS:
                continue
            ds = [d1]; d2 = second_entry(rule, d1, self.by_month[m], self.close)
            if d2 is not None and d2 <= end:
                ds.append(d2)
            for d in ds:
                r, why = self.ret(d, hold, target, stop)
                rows.append((m[0], m[1], r, why))
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
    assert score.index.max() <= pd.Timestamp('2023-12-31')
    sims = {s: Sim(s, intr, D) for s in L.STOCKS}
    valid = {s: panel[panel.stock == s].set_index('date').valid.to_dict() for s in L.STOCKS}
    f_ml = first_entries(sims['CNQ'].days, valid['CNQ'], score.to_dict())
    f_cal = {s: first_entries(sims[s].days, valid[s]) for s in L.STOCKS}
    res = {}
    for rule in SECOND:
        for T in TARGETS:
            for st in STOPS:
                for H in HOLDS:
                    t, per = sims['CNQ'].campaign(f_ml, rule, H, T, st)
                    G = float(t.ret.mean()); WR = float((t.ret > 0).mean() * 100)
                    margin = min(min(p['S'], p['GM']) - p['need'] for p in per.values())
                    a_ok = margin >= 1 and G >= 1.25 and WR >= 55
                    passed = 0; allr = []; xs = {}
                    for s in L.STOCKS:
                        ts, ps = sims[s].campaign(f_cal[s], rule, H, T, st); allr.append(ts.ret)
                        xs[s] = {y: [p['S'], p['GM'], p['need']] for y, p in ps.items()}
                        passed += sum(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in ps.values())
                    Gx = float(pd.concat(allr).mean())
                    b_ok = passed >= 14 and Gx >= 1.0
                    key = json.dumps(dict(second=rule, target=T, stop=st, hold=H), sort_keys=True)
                    res[key] = dict(cnq=dict(n=int(len(t)), G=round(G, 3), WR=round(WR, 1), worst=round(float(t.ret.min()), 1),
                                             stops=int((t.why == 'stop').sum()), per_year=per, margin=int(margin)),
                                    cross=dict(stock_years_passed=int(passed), of=18, G=round(Gx, 3), per_stock=xs),
                                    gate_A=bool(a_ok), gate_B=bool(b_ok), eligible=rule != 'same',
                                    passes=bool(a_ok and b_ok and rule != 'same'))
    order = sorted(res.items(), key=lambda kv: (-kv[1]['cnq']['margin'], -kv[1]['cross']['stock_years_passed'], -kv[1]['cnq']['G']))
    print('second target stop hold |  n     G    WR  worst stops | S by year | GM by year | need | margin | cross x/18  G | A B', flush=True)
    for k, v in order[:40]:
        c = json.loads(k); p = v['cnq']['per_year']
        print(f"{c['second']:6s} {c['target']:4.1f} {c['stop']:4.0f} {c['hold']:3d} | {v['cnq']['n']:3d} {v['cnq']['G']:6.2f} {v['cnq']['WR']:5.1f} {v['cnq']['worst']:6.1f} {v['cnq']['stops']:3d} | "
              f"{[x['S'] for x in p.values()]} | {[x['GM'] for x in p.values()]} | {[x['need'] for x in p.values()]} | {v['cnq']['margin']:+d} | "
              f"{v['cross']['stock_years_passed']:2d} {v['cross']['G']:5.2f} | {'A' if v['gate_A'] else '-'} {'B' if v['gate_B'] else '-'} {'' if v['eligible'] else '(same-day, not eligible)'}", flush=True)
    passers = {k: v for k, v in res.items() if v['passes']}
    same = {k: v for k, v in res.items() if not v['eligible'] and v['gate_A'] and v['gate_B']}
    out = dict(cutoff=cut, data_last_day=str(cal.max().date()), n_settings=len(res), gate=__doc__.split('GATE (pre-registered)')[1].split('Family searched')[0].strip(),
               passers=sorted(passers), same_day_settings_that_would_pass=sorted(same), settings=res)
    if passers:
        best = max(passers, key=lambda k: (passers[k]['cnq']['margin'], passers[k]['cross']['stock_years_passed'], passers[k]['cnq']['G']))
        out['chosen'] = json.loads(best); out['chosen_stats'] = passers[best]; print('CHOSEN', best, flush=True)
    json.dump(out, open(f'{RES}/stage13_round11_gate_search.json', 'w'), indent=1, default=str)
    print('eligible passers', len(passers), 'of', sum(v['eligible'] for v in res.values()), '| same-day settings clearing A and B:', len(same), flush=True)


if __name__ == '__main__':
    main()
