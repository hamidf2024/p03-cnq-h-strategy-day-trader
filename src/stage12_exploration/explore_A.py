# Stage 12 design exploration, kept for the record. TRAINING YEARS ONLY (rows before 2024-01-01).
# These scripts are how the candidate designs were found; none of them reads 2024-2026.
# TRAINING YEARS ONLY. Hard cut at 2024-01-01 before anything is computed.
import sys; sys.path.insert(0,'src')  # run from the repository root: python3 src/stage12_exploration/<file>
import numpy as np, pandas as pd, itertools
from s12_lib import *
df5=load_5min(end='2024-01-01')
base=build_daily(df5)
print(base.shape, base.index[0], base.index[-1], 'missing p:', base.p.isna().sum())
base.to_pickle('/tmp/stage12_daily_train_base.pkl')
rows=[]
for span in (10,20):
    d=add_features(base,span)
    for k,H,zx,st in itertools.product((1.0,1.5,2.0),(5,10),(None,0.0),(None,3.0)):
        sig=(d.z<=-k).values
        tr=simulate(d,sig,H=H,z_exit=zx,stop_atr=st)
        if len(tr)==0: continue
        tr['yr']=tr.entry_date.dt.year
        rec=dict(span=span,k=k,H=H,zx=zx,st=st)
        s=stats(tr); rec.update(n=s['n'],avg=round(s['avg'],2),win=round(s['win'],0),pf=round(s['pf'],2),days=round(s['days'],1))
        for y in (2020,2021,2022,2023):
            t=tr[tr.yr==y]; dy=d[d.index.year==y]
            if len(t):
                hold=t.days.mean()
                drift=(dy.c.iloc[-1]/dy.c.iloc[0]-1)*100/len(dy)*hold
                rec[f'n{y}']=len(t); rec[f'a{y}']=round(t.ret.mean(),2); rec[f'x{y}']=round(t.ret.mean()-drift,2)
        rows.append(rec)
R=pd.DataFrame(rows)
pd.set_option('display.width',250); pd.set_option('display.max_rows',200)
print(R.to_string())
