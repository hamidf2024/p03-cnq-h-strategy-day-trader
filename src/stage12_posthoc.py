"""
Stage 12 POST-HOC description of the blind result. Run AFTER the single blind
test. Nothing here was or may be used to select, tune or re-run a model on
2024-2026: it only describes what the frozen models did, and independently
re-checks the trade arithmetic.
"""
import sys, os, json, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from s12_lib import load_5min, build_daily, add_features, FEATURES
from stage12_field_fusion import pred_gbm, fwd, spring_signal

out = {}
df5 = load_5min(); base = build_daily(df5)
tr = pd.read_csv('results/experiments/stage12_blind_trades.csv', parse_dates=['entry_date', 'exit_date'])

# 1. independent arithmetic check of every blind trade against the raw 5-minute file
raw = pd.read_csv('data/raw/CNQ_5min_20200727_to_20261118.csv', parse_dates=['Datetime'])
raw['date'] = raw.Datetime.dt.normalize()
last_close = raw.groupby('date').Close.last()
days = list(last_close.index)
bad = 0
for r in tr.itertuples():
    e = last_close[r.entry_date]; x = last_close[r.exit_date]
    gap = days.index(r.exit_date) - days.index(r.entry_date)
    if abs(e - r.entry) > 1e-9 or abs(x - r.exit) > 1e-9 or abs((x / e - 1) * 100 - r.ret) > 1e-9 or gap != r.days:
        bad += 1
out['arithmetic_check'] = dict(trades=int(len(tr)), mismatches=int(bad))
print('arithmetic check:', out['arithmetic_check'])
# no overlapping positions within a model
ov = 0
for m, g in tr.groupby('model'):
    g = g.sort_values('entry_date')
    ov += int((g.entry_date.values[1:] <= g.exit_date.values[:-1]).sum())
out['overlapping_positions'] = ov
print('overlapping positions:', ov)

# 2. B's ranking skill on blind days, by year (descriptive)
frozen = pickle.load(open('results/experiments/stage12_frozen.pkl', 'rb'))
d = add_features(base, 20); yrs = d.index.year.values
ok = d[FEATURES].notna().all(1).values
p = np.full(len(d), np.nan); p[ok] = pred_gbm(frozen['B']['models'], d[FEATURES].values[ok])
y = fwd(d, 5).values
out['B_rank_ic_by_year'] = {}
for Y in (2024, 2025, 2026):
    m = ok & (yrs == Y) & np.isfinite(y)
    out['B_rank_ic_by_year'][Y] = round(float(pd.Series(p[m]).corr(pd.Series(y[m]), method='spearman')), 3)
m = ok & (yrs >= 2024) & np.isfinite(y)
q = pd.qcut(p[m], 5, labels=False)
out['B_blind_quintile_avg_5d_ret'] = [round(float(y[m][q == i].mean()), 3) for i in range(5)]
print('B rank IC by year:', out['B_rank_ic_by_year'], '| avg 5-day return by prediction quintile (low->high):', out['B_blind_quintile_avg_5d_ret'])

# 3. what happened to A: path after entry (descriptive)
dA = add_features(base, frozen['A']['span'])
a = tr[tr.model == 'A_spring_release']
c = dA.c
paths = []
for r in a.itertuples():
    i = c.index.get_loc(r.entry_date)
    paths.append([(c.iloc[min(i + k, len(c) - 1)] / c.iloc[i] - 1) * 100 for k in (1, 2, 3, 5, 10)])
P = pd.DataFrame(paths, columns=['d1', 'd2', 'd3', 'd5', 'd10'])
out['A_avg_path_after_entry_pct'] = {k: round(float(v), 2) for k, v in P.mean().items()}
out['A_trades_by_vol_regime'] = {}
v = dA.vol20.reindex(a.entry_date).values
med = float(np.nanmedian(dA.vol20[dA.index.year < 2024]))
hi = v > med
out['A_trades_by_vol_regime'] = dict(train_median_daily_vol_pct=round(med * 100, 2),
    high_vol=dict(n=int(hi.sum()), avg=round(float(a.ret.values[hi].mean()), 2)),
    low_vol=dict(n=int((~hi).sum()), avg=round(float(a.ret.values[~hi].mean()), 2)))
print('A average path after entry:', out['A_avg_path_after_entry_pct'], '| by vol regime:', out['A_trades_by_vol_regime'])

# 4. context
blind = d[yrs >= 2024]
out['context'] = dict(avg_daily_range_pct=round(float(((blind.h - blind.l) / blind.o).mean() * 100), 2),
                      daily_vol_pct=round(float(np.log(blind.c).diff().std() * 100), 2),
                      train_daily_vol_pct=round(float(np.log(d.c[yrs < 2024]).diff().std() * 100), 2),
                      year_returns_pct={int(Y): round(float((blind.c[blind.index.year == Y].iloc[-1] / blind.c[blind.index.year == Y].iloc[0] - 1) * 100), 1) for Y in (2024, 2025, 2026)})
print('context:', out['context'])
json.dump(out, open('results/experiments/stage12_posthoc_description.json', 'w'), indent=1)
