# Stage 12 design exploration, kept for the record. TRAINING YEARS ONLY (rows before 2024-01-01).
# These scripts are how the candidate designs were found; none of them reads 2024-2026.
# TRAINING YEARS ONLY (hard cut 2024-01-01).
import sys; sys.path.insert(0,'src')  # run from the repository root: python3 src/stage12_exploration/<file>
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from s12_lib import *
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
base=pd.read_pickle('/tmp/stage12_daily_train_base.pkl')
d=add_features(base,20)
for H in (5,10):
    d[f'f{H}']=(d.c.shift(-H)/d.c-1)*100
X=d[FEATURES]
ok=X.notna().all(1)
print('usable days',ok.sum(), 'first', d.index[ok][0])
# univariate ICs on all training (in-sample, descriptive only)
print('univariate Spearman IC with f5 / f10 (in-sample 2020-2023):')
ics=[]
for f in FEATURES:
    m=ok&d.f10.notna()
    ics.append((f, spearmanr(d.loc[m,f],d.loc[m,'f5'])[0], spearmanr(d.loc[m,f],d.loc[m,'f10'])[0]))
for f,a,b in sorted(ics,key=lambda t:-abs(t[2])): print(f'  {f:12s} {a:+.3f} {b:+.3f}')
for H in (5,10):
    for Y in (2021,2022,2023):
        tr=ok&(d.index.year<Y)&d[f'f{H}'].notna()
        # purge: drop last H training days whose label overlaps the validation year
        tr_idx=np.where(tr)[0]
        last_tr=np.where(d.index.year<Y)[0].max()
        tr_idx=tr_idx[tr_idx<=last_tr-H]
        te=ok&(d.index.year==Y)&d[f'f{H}'].notna()
        if len(tr_idx)<40: print(H,Y,'too few',len(tr_idx)); continue
        Xtr=X.iloc[tr_idx]; ytr=d[f'f{H}'].iloc[tr_idx]; mu=ytr.mean()
        Xte=X[te]; yte=d.loc[te,f'f{H}']
        out=[f'H={H} val={Y} ntr={len(tr_idx)} nte={te.sum()} drift_te={yte.mean():+.2f}']
        for name,mdl in (('gbm',GradientBoostingRegressor(n_estimators=60,max_depth=2,learning_rate=0.05,subsample=0.8,random_state=0)),
                         ('ridge',None)):
            if mdl is None:
                sc=StandardScaler().fit(Xtr); mdl=RidgeCV(alphas=[10,100,1000]).fit(sc.transform(Xtr).clip(-4,4),ytr-mu); pr=mdl.predict(sc.transform(Xte).clip(-4,4))
            else:
                mdl.fit(Xtr,ytr-mu); pr=mdl.predict(Xte)
            ic=spearmanr(pr,yte)[0]
            q=np.quantile(pr,0.8); top=yte[pr>=q].mean()-yte.mean()
            q2=np.quantile(pr,0.2); bot=yte[pr<=q2].mean()-yte.mean()
            out.append(f'{name}: IC={ic:+.3f} top20%x={top:+.2f} bot20%x={bot:+.2f}')
        print(' | '.join(out))
