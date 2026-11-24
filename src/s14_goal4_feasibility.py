"""
Stage 14, goal-4 feasibility (training years only, test years removed): can ANY design in a wide family of
many-trades-per-month CNQ campaigns reach level 1 on all four goals, with goal 4 in its 2026-11-24 form
(8 months a year whose trades total 5% or more, with at most MAX_NEG losing months, each no worse than WORST)?

The settings are chosen on the same years they are scored on, so this is an upper bound: if nothing passes
here, nothing would pass honestly. Entries use the out-of-fold Stage 14 forecasts (each day forecast by a
model trained only on earlier rows), so the forecasts themselves are not fitted to the day they score.

Family: enter at the close of every day whose forecast rank (5- or 20-session model, old or old+new
features) is at least q; each entry $1,000; at most K open at once; exit at target T, stop s, or after
`hold` sessions. Optionally all trades are closed by the last session of their entry month, and a month
stops taking new trades once its closed trades have lost more than 1.5% (a monthly loss budget).
Run with S13_CUTOFF=2023-12-29.
"""
import json, os, pickle, sys
import numpy as np, pandas as pd
import s13_lib as L
from stage13_two_buys import Tape

RES = os.environ.get('S13_OUT', 'results/experiments')
# goal 4 negative-month rule: owner's third form of 2026-11-24 (at most two losing months a year, each no worse than -3%).
# The first run of this script used the second form (one month, -2%); its result is kept in the JSON under 'earlier_rule'.
MAX_NEG, WORST = int(os.environ.get('GM_MAX_NEG', 2)), float(os.environ.get('GM_WORST', -3.0))
YEARS = [2021, 2022, 2023]


def main():
    cut = os.environ.get('S13_CUTOFF', ''); assert cut and cut <= '2023-12-31'
    intr = L.load_5min('CNQ'); D = L.daily(intr); assert D.index.max() <= pd.Timestamp('2023-12-31')
    tape = Tape(intr, D)
    oof = pickle.load(open(f'{RES}/stage14_oof_predictions_LOCAL_ONLY.pkl', 'rb'))
    import stage13_peer_fusion as P
    ranks = {}
    for (H, name), q in oof.items():
        s = q[q.stock == 'CNQ'].set_index('date').pred.sort_index()
        ranks[(H, name)] = P.trailing_rank(s)
    days = tape.days; pos = tape.pos
    month_last = pd.Series(days).groupby([d.to_period('M') for d in days]).max().to_dict()
    cache = {}

    def trade(d, hold, T, s, month_end):
        key = (d, hold, T, s, month_end)
        if key not in cache:
            h = hold
            if month_end:
                h = min(hold, pos[month_last[d.to_period('M')]] - pos[d])
                if h < 1:
                    cache[key] = None; return None
            e, xd, px, why = tape.buy(d, len(tape.bars[d][0]) - 1, h, T, s)
            cache[key] = ((px / e - 1) * 100, xd, why)
        return cache[key]

    res = []
    end = days[-21]
    for (H, name), rk in ranks.items():
        cand = [d for d, v in rk.items() if not np.isnan(v) and d in pos and d <= end and d.year in YEARS]
        first = min(cand) if cand else None
        avail = {2021: 12 - first.month + 1, 2022: 12, 2023: int(end.month)}
        for q in (0.5, 0.7, 0.85):
            sig = [d for d in cand if rk[d] >= q]
            for T in (1.0, 2.0, 3.0, 4.0):
                for s in (1.0, 2.0, 3.0, 5.0, 15.0):
                    for hold in (5, 10, 20):
                        for K in (1, 3, 5):
                            for month_end in (False, True):
                                for budget in (False, True):
                                    open_exits = []; rows = []; mloss = {}
                                    for d in sig:
                                        open_exits = [x for x in open_exits if x > d]
                                        if len(open_exits) >= K:
                                            continue
                                        m = d.to_period('M')
                                        if budget and mloss.get(m, 0.0) < -1.5:
                                            continue
                                        r = trade(d, hold, T, s, month_end)
                                        if r is None:
                                            continue
                                        ret, xd, why = r; open_exits.append(xd); rows.append((d.year, d.month, ret, why))
                                        if budget:
                                            mloss[m] = mloss.get(m, 0.0) + ret     # closed-trade loss of the month (conservative: counted at entry)
                                    if len(rows) < 20:
                                        continue
                                    t = pd.DataFrame(rows, columns=['y', 'm', 'ret', 'why'])
                                    per = {}
                                    for y in YEARS:
                                        g = t[t.y == y].groupby('m').ret; tot = g.sum(); need = int(np.ceil(8 / 12 * avail[y]))
                                        neg = int((tot.round(2) < 0).sum()); worst = float(tot.min()) if len(tot) else 0.0
                                        per[y] = dict(n=int((t.y == y).sum()), S=int((g.mean() > 1).sum()), GM5=int((tot >= 5).sum()), neg=neg, worst=round(worst, 2),
                                                      need=need, gm_ok=bool(int((tot >= 5).sum()) >= need and neg <= MAX_NEG and round(worst, 2) >= WORST))
                                    G = float(t.ret.mean()); WR = float((t.ret > 0).mean() * 100)
                                    l1 = G >= 1 and WR >= 50 and all(p['S'] >= p['need'] and p['gm_ok'] for p in per.values())
                                    res.append(dict(src=f'H{H} {name}', q=q, T=T, stop=s, hold=hold, K=K, month_end=month_end, budget=budget, n=int(len(t)),
                                                    G=round(G, 3), WR=round(WR, 1), S=[p['S'] for p in per.values()], GM5=[p['GM5'] for p in per.values()],
                                                    neg=[p['neg'] for p in per.values()], worst=[p['worst'] for p in per.values()], need=[p['need'] for p in per.values()],
                                                    years_gm_ok=sum(p['gm_ok'] for p in per.values()), level1_all_four=bool(l1)))
        print('done', H, name, len(res), flush=True)
    r = pd.DataFrame(res)
    r['min_neg'] = r.neg.apply(max); r['worst_month'] = r.worst.apply(min)
    print('settings scored:', len(r), '| level 1 on all four in every training year:', int(r.level1_all_four.sum()))
    print('settings with at least one training year that keeps goal 4:', int((r.years_gm_ok >= 1).sum()), '| two years:', int((r.years_gm_ok >= 2).sum()), '| three:', int((r.years_gm_ok == 3).sum()))
    print('fewest losing months in the worst year, over all settings:', int(r.min_neg.min()))
    best = r.sort_values(['years_gm_ok', 'min_neg', 'worst_month', 'G'], ascending=[False, True, False, False]).head(12)
    print(best[['src', 'q', 'T', 'stop', 'hold', 'K', 'month_end', 'budget', 'n', 'G', 'WR', 'S', 'GM5', 'neg', 'worst', 'years_gm_ok']].to_string(index=False))
    g1 = r[(r.G >= 1)]
    print('\namong settings with G >= 1%:', len(g1), '| fewest losing months in worst year:', int(g1.min_neg.min()) if len(g1) else None)
    print(g1.sort_values(['min_neg', 'worst_month'], ascending=[True, False]).head(6)[['src', 'q', 'T', 'stop', 'hold', 'K', 'month_end', 'budget', 'n', 'G', 'WR', 'S', 'GM5', 'neg', 'worst']].to_string(index=False))
    # what CNQ itself does: months in which simply holding CNQ gained or lost
    mret = D.close.resample('ME').last().pct_change().dropna() * 100; mret = mret[mret.index.year.isin(YEARS)]
    hold_stats = {int(y): dict(up_months=int((g > 0).sum()), down_months=int((g < 0).sum()), months_below_minus2=int((g < -2).sum()), months_above_5=int((g >= 5).sum()))
                  for y, g in mret.groupby(mret.index.year)}
    print('\nholding CNQ, by year:', hold_stats)
    prev = json.load(open(f'{RES}/stage14_goal4_feasibility.json')) if os.path.exists(f'{RES}/stage14_goal4_feasibility.json') else {}
    earlier = prev.get('earlier_rule') or ({k: prev[k] for k in ('n_settings', 'level1_all_four', 'settings_with_years_keeping_goal4', 'fewest_losing_months_in_worst_year')} | {'rule': 'at most one losing month, no worse than -2%'} if prev else None)
    out = dict(rule=f'at most {MAX_NEG} losing months a year, each no worse than {WORST}%', earlier_rule=earlier, cutoff=cut, n_settings=int(len(r)), level1_all_four=int(r.level1_all_four.sum()),
               settings_with_years_keeping_goal4={k: int((r.years_gm_ok >= k).sum()) for k in (1, 2, 3)},
               fewest_losing_months_in_worst_year=int(r.min_neg.min()), cnq_buy_and_hold_months=hold_stats,
               best=best.drop(columns=['min_neg', 'worst_month']).to_dict('records'))
    json.dump(out, open(f'{RES}/stage14_goal4_feasibility.json', 'w'), indent=1, default=str)


if __name__ == '__main__':
    main()
