# Stage 12 design exploration, kept for the record. TRAINING YEARS ONLY (rows before 2024-01-01).
# These scripts are how the candidate designs were found; none of them reads 2024-2026.
# Exploration on TRAINING YEARS ONLY (2020-07-27 .. 2023-12-31). No 2024+ rows are loaded.
import pandas as pd, numpy as np
df=pd.read_csv('data/raw/CNQ_5min_20200727_to_20261118.csv',parse_dates=['Datetime'])
df=df[df.Datetime<'2024-01-01'].copy()
df['date']=df.Datetime.dt.date
g=df.groupby('date')
d=pd.DataFrame({'o':g.Open.first(),'h':g.High.max(),'l':g.Low.min(),'c':g.Close.last(),'v':g.Volume.sum(),'n':g.Close.size()})
d.index=pd.to_datetime(d.index)
print(len(d), d.index[0], d.index[-1]); print(d.n.describe())
r=np.log(d.c).diff()
print('daily vol %',r.std()*100,'mean daily ret %',r.mean()*100, 'range% mean',((d.h-d.l)/d.o).mean()*100)
print(d.c.resample('YE').agg(['first','last','mean']))
# autocorrelation / variance ratio
for k in [1,2,3,5,10,20]:
    rk=np.log(d.c).diff(k)
    print('VR',k, (rk.var()/(k*r.var())).round(3), 'ac1 of r lag',k, r.autocorr(k).round(3))
# conditional forward returns after n-day drops (z-scored by 20d vol)
vol=r.rolling(20).std().shift(1)
for look in [2,3,5]:
    z=(np.log(d.c).diff(look))/(vol*np.sqrt(look))
    for thr in [-1.0,-1.5,-2.0]:
        m=z<thr
        out=[]
        for fwd in [1,3,5,10]:
            f=(d.c.shift(-fwd)/d.c-1)[m]
            out.append(f"{fwd}d:{f.mean()*100:+.2f}%({(f>0).mean()*100:.0f}%)")
        print(f'look{look} z<{thr}: n={m.sum()}', ' '.join(out))
print('unconditional', ' '.join(f"{fwd}d:{(d.c.shift(-fwd)/d.c-1).mean()*100:+.2f}%" for fwd in [1,3,5,10]))
d.to_pickle('/tmp/stage12_daily_train_explore.pkl')
