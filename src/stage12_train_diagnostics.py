"""
Stage 12 diagnostics on the TRAINING YEARS ONLY (hard cut 2024-01-01), run
after the config was frozen and before the blind test. Nothing here is used
for selection; it only asks whether the frozen Spring-release config sits on
a knife-edge and whether random entry days would have done as well.
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from s12_lib import load_5min, build_daily, add_features, simulate
from stage12_field_fusion import spring_signal, year_drift, add_excess, tstat, TRAIN_END

df5 = load_5min(end=TRAIN_END)
base = build_daily(df5)
out = {}
SPAN, K, H = 10, 1.5, 5
d = add_features(base, SPAN)
yrs = d.index.year.values
val = np.isin(yrs, (2021, 2022, 2023))

def run(sig, H=H, dd=d):
    tr = add_excess(simulate(dd, sig, H=H), year_drift(dd, H))
    return tr[tr.yr.isin((2021, 2022, 2023))]

tr0 = run(spring_signal(d, K))
print(f'frozen config span={SPAN} k={K} H={H}: n={len(tr0)} avg={tr0.ret.mean():+.2f}% excess={tr0.excess.mean():+.2f}%')

# 1. neighbourhood (not used for selection)
nb = []
for span in (8, 10, 12, 15):
    dd = add_features(base, span)
    for k in (1.25, 1.5, 1.75):
        for h in (3, 4, 5, 6, 7):
            t = run(spring_signal(dd, k), h, dd)
            nb.append(dict(span=span, k=k, H=h, n=len(t), avg=round(t.ret.mean(), 2), excess=round(t.excess.mean(), 2),
                           t=round(tstat(t.excess), 2), pos_years=int(sum(t[t.yr == y].excess.mean() > 0 for y in (2021, 2022, 2023)))))
NB = pd.DataFrame(nb)
print(NB.to_string(index=False))
out['neighbourhood'] = nb
out['neighbourhood_summary'] = dict(configs=len(NB), share_positive_excess=float((NB.excess > 0).mean()),
                                    share_positive_all_3_years=float((NB.pos_years == 3).mean()),
                                    median_excess=float(NB.excess.median()), median_avg=float(NB.avg.median()))
print(out['neighbourhood_summary'])

# 2. permutation test: same number of entry days per year, chosen at random
rng = np.random.default_rng(12)
obs = tr0.ret.mean()
n_by_year = tr0.groupby('yr').size().to_dict()
c = d.c.values
fw = (pd.Series(c).shift(-H) / pd.Series(c) - 1).values * 100
sims = []
for _ in range(20000):
    rets = []
    for y, n in n_by_year.items():
        idx = np.where((yrs == y) & np.isfinite(fw))[0]
        # non-overlapping random entries: sample and enforce spacing > H
        pick = np.sort(rng.choice(idx, n, replace=False))
        rets.extend(fw[pick])
    sims.append(np.mean(rets))
sims = np.array(sims)
p = float((sims >= obs).mean())
out['permutation'] = dict(observed_avg=round(float(obs), 3), random_mean=round(float(sims.mean()), 3),
                          random_95pct=round(float(np.quantile(sims, 0.95)), 3), p_value=round(p, 4), draws=20000)
print('permutation test (random entry days, same count per year):', out['permutation'])

# 3. what each ingredient contributes (ablation, training years)
abl = {}
abl['stretch only (enter first stretched day)'] = run((d.z <= -K).fillna(False).values)
zmin3 = d.z.rolling(3).min()
abl['stretch within 3 days, no turn test'] = run(((zmin3 <= -K) & (d.z < 0)).fillna(False).values)
abl['turn only (dz>0, z<0), no stretch'] = run(((d.dz > 0) & (d.z < 0)).fillna(False).values)
abl['full rule'] = tr0
out['ablation'] = {}
for k_, t in abl.items():
    out['ablation'][k_] = dict(n=len(t), avg=round(float(t.ret.mean()), 2), excess=round(float(t.excess.mean()), 2),
                               win=round(float((t.ret > 0).mean() * 100), 1), t_excess=round(tstat(t.excess), 2))
    print(f'  {k_:45s}', out['ablation'][k_])
json.dump(out, open('results/experiments/stage12_train_diagnostics.json', 'w'), indent=1)
