"""Stage 13, step 0: what would level 1 (G1 + WR1 + S1) take? Training years only (2020-2023).
Uses CNQ's real forward returns and asks how often the direction must be right."""
import json, pickle, os
import numpy as np, pandas as pd
import s13_lib as L

RES = os.environ.get('S13_OUT', 'results/experiments')
CACHE = f'{RES}/stage13_panel_cache.pkl'                 # holds prices: local only, never committed
if os.path.exists(CACHE):
    panel, D, intr = pickle.load(open(CACHE, 'rb'))
else:
    panel, D, intr = L.build_panel(); pickle.dump((panel, D, intr), open(CACHE, 'wb'))
c = panel[(panel.stock == 'CNQ') & panel.valid & (panel.date <= L.TRAIN_END) & (panel.date >= '2020-11-01')].set_index('date')
rng = np.random.default_rng(13)
res = {'period': '2020-11-01 to 2023-12-31', 'days': int(len(c)), 'baseline': {}, 'required_skill': []}
for H in (5, 10):
    f = c[f'fwd{H}'].dropna()
    m = f.groupby(f.index.strftime('%Y-%m')).mean()
    res['baseline'][f'always_long_{H}d'] = dict(avg_pct=round(float(f.mean()), 3), win_rate=round(float((f > 0).mean() * 100), 1),
                                                 sd_pct=round(float(f.std()), 2), share_of_months_avg_above_1pct=round(float((m > 1).mean()), 3))
    months = sorted(set(f.index.strftime('%Y-%m')))
    by_month = {mm: f[f.index.strftime('%Y-%m') == mm].values for mm in months}
    for per_month in (1, 2, 4):
        for p in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90):
            hits, G, W = [], [], []
            for _ in range(400):
                h = 0; rets = []
                for mm in months:
                    x = rng.choice(by_month[mm], size=min(per_month, len(by_month[mm])), replace=False)
                    right = rng.random(len(x)) < p
                    r = np.where(right, np.abs(x), -np.abs(x))          # trade in the right direction with probability p
                    rets.extend(r); h += r.mean() > 1
                hits.append(12 * h / len(months)); G.append(np.mean(rets)); W.append(np.mean(np.array(rets) > 0) * 100)
            res['required_skill'].append(dict(hold_days=H, trades_per_month=per_month, direction_right_pct=int(p * 100),
                                              avg_pct_per_trade=round(float(np.mean(G)), 2), win_rate=round(float(np.mean(W)), 1),
                                              months_above_1pct_per_12=round(float(np.mean(hits)), 1),
                                              chance_of_8_of_12=round(float(np.mean(np.array(hits) >= 8)), 2)))
json.dump(res, open(f'{RES}/stage13_feasibility.json', 'w'), indent=1)
print(json.dumps(res['baseline'], indent=1))
t = pd.DataFrame(res['required_skill'])
print(t[t.hold_days == 5].to_string(index=False)); print(t[(t.hold_days == 10) & (t.trades_per_month <= 2)].to_string(index=False))
print(panel.groupby('stock').valid.sum().to_dict(), len(L.feature_names(panel)))
