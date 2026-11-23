"""Stage 14 preparation.
1. Leak check: build the feature panel twice, once from all data and once from data cut off at 2023-12-29,
   and compare every feature on every day up to the cut-off. Identical values mean no feature can see
   2024-2026.
2. Search for settings that reach level 2 or level 3 on each of 2021, 2022, 2023, run with the test years
   removed from the data altogether (S13_CUTOFF), so the search cannot touch them.
Usage: python3 src/s13_leak_check_and_search.py   (env S13_DATA, S13_OUT as for stage13_peer_fusion.py)"""
import json, os, pickle
import numpy as np, pandas as pd
RES = os.environ.get('S13_OUT', 'results/experiments')
CUT = '2023-12-29'
import s13_lib as L
full, _, _ = L.build_panel()
os.environ['S13_CUTOFF'] = CUT
panel, D, intr = L.build_panel()
feats = L.feature_names(panel)
a = full[full.date <= CUT].reset_index(drop=True)[feats].astype(float).values
b = panel[panel.date <= CUT].reset_index(drop=True)[feats].astype(float).values
same = bool(a.shape == b.shape and np.allclose(a, b, rtol=1e-12, atol=1e-12, equal_nan=True))
fr = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
report = dict(features_identical_with_test_years_removed=same, features=len(feats), rows_compared=int(a.shape[0]),
              final_models_trained_to={str(H): m['train_last'] for H, m in fr['finals'].items()},
              out_of_fold_predictions_span=[str(fr['oof'][5].index.min().date()), str(fr['oof'][5].index.max().date())],
              last_day_in_search_data=str(panel.date.max().date()))
print(json.dumps(report), flush=True)
assert same and panel.date.max() <= pd.Timestamp(CUT)

cal = D['USO'].index; cnq = panel[panel.stock == 'CNQ'].set_index('date')
path = L.Path(intr['CNQ'], D['CNQ'])
g = fr['oof'][5]['gbm']
sc = pd.Series([np.nan if i < 40 or np.isnan(v) else (g.values[max(0, i - 120):i] < v).mean() for i, v in enumerate(g.values)], index=g.index)
def monthly(cond):
    out = pd.Series(0.0, index=cal); done = set()
    for d in sc.index:
        m = (d.year, d.month)
        if m not in done and cond(d):
            out[d] = 1; done.add(m)
    return out
entries = {'model at least neutral': monthly(lambda d: sc[d] >= 0.5), 'model favourable': monthly(lambda d: sc[d] >= 0.7),
           'neutral and price below its 20-day average': monthly(lambda d: sc[d] >= 0.5 and cnq.z20.get(d, 0) <= -0.5)}
rows = []
for en, sig in entries.items():
    for tgt in (3.0, 4.0, 5.0, 6.0, 8.0):
        for stop in (5.0, 10.0, 15.0):
            for hold in (20, 40, 60):
                end = cal[-hold - 1]
                t = L.run_trades(path, sig, hold, tgt, stop, start='2021-01-01', end=str(end.date()), overlap=True)
                per = {}
                for y in (2021, 2022, 2023):
                    ty = t[t.entry_date.dt.year == y]; avail = 12 if y < 2023 else end.month
                    ma = ty.groupby(ty.entry_date.dt.month).ret.mean()
                    per[y] = dict(n=len(ty), G=float(ty.ret.mean()) if len(ty) else -9, WR=float((ty.ret > 0).mean() * 100) if len(ty) else 0,
                                  S=int((ma > 1).sum()), avail=int(avail))
                l2 = all(p['G'] >= 2 and p['WR'] >= 65 and p['S'] >= round(10 / 12 * p['avail']) for p in per.values())
                l3 = all(p['G'] > 3 and p['WR'] > 75 and p['S'] >= p['avail'] for p in per.values())
                rows.append(dict(entry=en, target=tgt, stop=stop, hold=hold, n=len(t), G=round(float(t.ret.mean()), 2), WR=round(float((t.ret > 0).mean() * 100), 1),
                                 S=[per[y]['S'] for y in per], G_by_year=[round(per[y]['G'], 2) for y in per], level2_every_year=l2, level3_every_year=l3,
                                 worst=round(float(t.ret.min()), 1)))
r = pd.DataFrame(rows)
report['settings_searched'] = len(r); report['level2_in_every_training_year'] = int(r.level2_every_year.sum()); report['level3_in_every_training_year'] = int(r.level3_every_year.sum())
report['best_by_steadiness'] = r.assign(k=r.S.map(min)).sort_values(['k', 'G'], ascending=False).drop(columns='k').head(8).to_dict('records')
json.dump(report, open(f'{RES}/stage14_leak_check_and_level_search.json', 'w'), indent=1)
print('searched', len(r), 'level2', report['level2_in_every_training_year'], 'level3', report['level3_in_every_training_year'])
print(r.assign(k=r.S.map(min)).sort_values(['k', 'G'], ascending=False).head(8)[['entry', 'target', 'stop', 'hold', 'n', 'G', 'WR', 'S', 'G_by_year', 'worst']].to_string(index=False))
