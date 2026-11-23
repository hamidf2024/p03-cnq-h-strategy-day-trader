# Stage 12 design exploration, kept for the record. TRAINING YEARS ONLY (rows before 2024-01-01).
# These scripts are how the candidate designs were found; none of them reads 2024-2026.
# TRAINING YEARS ONLY (hard cut 2024-01-01). Horizon structure of the signal.
import sys; sys.path.insert(0,'src')  # run from the repository root: python3 src/stage12_exploration/<file>
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from s12_lib import *
from stage12_field_fusion import fit_gbm,pred_gbm,fit_ridge,pred_ridge,train_rows,fwd
base=pd.read_pickle('/tmp/stage12_daily_train_base.pkl'); d=add_features(base,20)
ok=d[FEATURES].notna().all(1).values; X=d[FEATURES].values; yrs=d.index.year.values
print('event study: mean excess %% (vs same-year avg) after z<=-k, by horizon; all event days (overlapping)')
for k in (1.0,1.5,2.0):
    for Y in (2021,2022,2023):
        m=(d.z<=-k).values&(yrs==Y)
        s=f'k={k} {Y} n={m.sum():3d}: '
        for H in (1,2,3,5,7,10,15,20):
            f=fwd(d,H); s+=f'{H}d {f[m].mean()-f[yrs==Y].mean():+.2f}  '
        print(s)
print('\nGBM / ridge fold rank-IC and top-quintile excess by horizon')
for H in (3,5,10,15,20):
    y=fwd(d,H).values
    for Y,years in ((2021,(2020,)),(2022,(2020,2021)),(2023,(2020,2021,2022))):
        last=np.where(np.isin(yrs,years))[0].max(); pos=train_rows(d,ok,years,H,last)
        if len(pos)<40: print(H,Y,'skip',len(pos)); continue
        te=ok&(yrs==Y)&np.isfinite(y)
        mu=y[pos].mean()
        out=f'H={H:2d} {Y} ntr={len(pos):3d}'
        for nm,fit,pred in (('gbm',fit_gbm,pred_gbm),('ridge',fit_ridge,pred_ridge)):
            m=fit(X[pos],y[pos]-mu); p=pred(m,X[te]); yt=y[te]
            ic=pd.Series(p).corr(pd.Series(yt),method='spearman')
            top=yt[p>=np.quantile(p,0.8)].mean()-yt.mean()
            out+=f' | {nm} IC {ic:+.3f} top20x {top:+.2f} pred_sd {p.std():.2f} frac(p>=1) {np.mean(p>=1):.2f} x|p>=1 {(yt[p>=1].mean()-yt.mean()) if (p>=1).any() else float("nan"):+.2f}'
        print(out)
