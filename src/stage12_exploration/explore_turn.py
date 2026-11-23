# Stage 12 design exploration, kept for the record. TRAINING YEARS ONLY (rows before 2024-01-01).
# These scripts are how the candidate designs were found; none of them reads 2024-2026.
# TRAINING YEARS ONLY (hard cut 2024-01-01). Does waiting for the turn help?
import sys; sys.path.insert(0,'src')  # run from the repository root: python3 src/stage12_exploration/<file>
import numpy as np, pandas as pd, warnings; warnings.filterwarnings('ignore')
from s12_lib import *
from stage12_field_fusion import fwd, year_drift, add_excess, tstat
base=pd.read_pickle('/tmp/stage12_daily_train_base.pkl')
for span in (10,20):
    d=add_features(base,span); yrs=d.index.year.values
    zmin3=d.z.rolling(3).min()        # stretched at any point in the last 3 days (incl. today)
    conds={
     'stretch now':            lambda k: (d.z<=-k),
     'stretch now & up day':   lambda k: (d.z<=-k)&(d.r1>0),
     'stretch now & dz>0':     lambda k: (d.z<=-k)&(d.dz>0),
     'stretch now & clv>.5':   lambda k: (d.z<=-k)&(d.clv>0.5),
     'stretched<=3d & up day': lambda k: (zmin3<=-k)&(d.r1>0)&(d.z<0),
     'stretched<=3d & dz>0':   lambda k: (zmin3<=-k)&(d.dz>0)&(d.z<0),
    }
    for name,fn in conds.items():
        for k in (1.0,1.5,2.0):
            sig=fn(k).fillna(False).values
            for H in (5,10):
                tr=simulate(d,sig,H=H)
                if len(tr)<3: continue
                tr=add_excess(tr,year_drift(d,H))
                s=f'span{span} {name:24s} k={k} H={H:2d} n={len(tr):3d} avg {tr.ret.mean():+.2f} x {tr.excess.mean():+.2f} t {tstat(tr.excess):+.2f} win {(tr.ret>0).mean()*100:.0f}% |'
                for Y in (2021,2022,2023):
                    t=tr[tr.yr==Y]; s+=f' {Y}: n{len(t):2d} x{t.excess.mean():+.2f}'
                print(s)
