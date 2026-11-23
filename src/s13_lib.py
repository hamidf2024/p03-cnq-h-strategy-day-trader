"""
Stage 13 library: daily panel for CNQ, five peers, an oil fund and the sector
fund, built from the local 5-minute files in data/raw/peers/; causal features;
a trade simulator that walks the 5-minute path (targets and stops).

Timing convention (same as Stage 12): the decision is taken one 5-minute bar
before the close, so every feature uses bars up to and including the 15:50
bar; entries and time exits are filled at the close of the 15:55 bar.
"""
import glob
import os
import numpy as np
import pandas as pd

DATA = os.environ.get('S13_DATA', 'data/raw/peers')
STOCKS = ['CNQ', 'SU', 'CVE', 'IMO', 'XOM', 'CVX']
AUX = ['USO', 'XLE']
TRAIN_END = '2023-12-31'
BLIND_START, BLIND_END = '2024-01-01', '2026-11-18'     # last entry day; same window as the goal scorecard
LAST_FULL_DAY = '2026-11-20'                            # 2026-11-23 is a partial session


def load_5min(sym):
    f = sorted(glob.glob(f'{DATA}/{sym}_5min_sip_*.csv'))[-1]
    df = pd.read_csv(f, usecols=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume'], parse_dates=['Datetime'])
    df['date'] = df.Datetime.dt.normalize()
    df = df[df.date <= LAST_FULL_DAY]
    n = df.groupby('date').Close.transform('size')
    return df[n >= 20].reset_index(drop=True)            # drops the three vendor gap days (single 09:30 bar)


def daily(df):
    """One row per day. p_dec = price at decision time; close = execution price."""
    tm = df.Datetime.dt.hour * 60 + df.Datetime.dt.minute
    pre = df[tm <= 950]                                   # bars up to 15:50
    g, gp = df.groupby('date'), pre.groupby('date')
    d = pd.DataFrame({'open': g.Open.first(), 'close': g.Close.last(), 'p_dec': gp.Close.last(),
                      'high': gp.High.max(), 'low': gp.Low.min(), 'vol': gp.Volume.sum()})
    r = np.log(pre.Close).groupby(pre.date).diff()
    d['rv'] = np.sqrt((r ** 2).groupby(pre.date).sum())  # realised volatility of the day, 5-minute returns
    last_hr = pre[tm[pre.index] >= 900].groupby('date').Open.first()
    d['p_1500'] = last_hr
    return d


def z(s, n):
    return (s - s.rolling(n).mean()) / s.rolling(n).std()


def roll_beta(y, x, n=60):
    return y.rolling(n).cov(x) / x.rolling(n).var()


def build_panel():
    """Returns (panel, dailies, intraday). panel: one row per (date, stock) with causal features."""
    intr = {s: load_5min(s) for s in STOCKS + AUX}
    D = {s: daily(intr[s]) for s in STOCKS + AUX}
    cal = D['USO'].index                                    # complete calendar
    D = {s: D[s].reindex(cal) for s in D}
    lp = pd.DataFrame({s: np.log(D[s].p_dec) for s in D})   # decision-time log prices
    r1 = lp.diff()
    uso, xle = lp['USO'], lp['XLE']
    rows = []
    for s in STOCKS:
        d = D[s]; p = lp[s]; f = pd.DataFrame(index=cal)
        others = [o for o in STOCKS if o != s]
        basket = lp[others].mean(axis=1)                    # equal-weight peer basket (log)
        for k in (1, 2, 3, 5, 10, 20, 60):
            f[f'r{k}'] = p.diff(k)
        f['overnight'] = np.log(d.open / d.close.shift(1))
        f['intraday'] = np.log(d.p_dec / d.open)
        f['last_hour'] = np.log(d.p_dec / d.p_1500)
        f['rv1'] = d.rv; f['rv5'] = d.rv.rolling(5).mean(); f['rv20'] = d.rv.rolling(20).mean()
        f['rv_ratio'] = f.rv5 / f.rv20
        f['range'] = np.log(d.high / d.low)
        f['closeloc'] = (d.p_dec - d.low) / (d.high - d.low).replace(0, np.nan)
        f['volz'] = z(np.log(d.vol.replace(0, np.nan)), 20)
        f['dist_hi20'] = p - p.rolling(20).max(); f['dist_lo20'] = p - p.rolling(20).min()
        f['z20'] = z(p, 20); f['z60'] = z(p, 60)
        f['vol20'] = r1[s].rolling(20).std()
        up = r1[s].clip(lower=0).rolling(14).mean(); dn = (-r1[s].clip(upper=0)).rolling(14).mean()
        f['rsi14'] = up / (up + dn)
        # relative to peers: return gaps and the residual "spring" (displacement from a rolling-beta fit)
        for k in (1, 3, 5, 10, 20):
            f[f'rel{k}'] = p.diff(k) - basket.diff(k)
        b = roll_beta(r1[s], basket.diff(), 60)
        res = (r1[s] - b.shift(1) * basket.diff())
        for k in (5, 10, 20):
            f[f'peer_res{k}'] = res.rolling(k).sum() / (res.rolling(60).std() * np.sqrt(k))
        f['peer_beta'] = b
        f['rank5'] = lp[STOCKS].diff(5).rank(axis=1)[s]; f['rank20'] = lp[STOCKS].diff(20).rank(axis=1)[s]
        # oil: fund returns and the stock's residual against oil
        for k in (1, 3, 5, 10, 20):
            f[f'oil{k}'] = uso.diff(k)
        f['oil_overnight'] = np.log(D['USO'].open / D['USO'].close.shift(1))
        f['oil_intraday'] = np.log(D['USO'].p_dec / D['USO'].open)
        f['oil_last_hour'] = np.log(D['USO'].p_dec / D['USO'].p_1500)
        f['oil_rv_ratio'] = D['USO'].rv.rolling(5).mean() / D['USO'].rv.rolling(20).mean()
        f['oil_z20'] = z(uso, 20)
        bo = roll_beta(r1[s], r1['USO'], 60)
        reso = r1[s] - bo.shift(1) * r1['USO']
        for k in (5, 10, 20):
            f[f'oil_res{k}'] = reso.rolling(k).sum() / (reso.rolling(60).std() * np.sqrt(k))
        f['oil_beta'] = bo
        f['corr_oil20'] = r1[s].rolling(20).corr(r1['USO'])
        # sector
        for k in (1, 5, 20):
            f[f'xle{k}'] = xle.diff(k)
        f['xle_rv_ratio'] = D['XLE'].rv.rolling(5).mean() / D['XLE'].rv.rolling(20).mean()
        f['dispersion5'] = lp[STOCKS].diff(5).std(axis=1)
        f['dow'] = cal.dayofweek; f['dom'] = cal.day
        f['is_cnq'] = float(s == 'CNQ')
        # labels: close-to-close forward returns, in % (execution prices)
        lc = np.log(D[s].close)
        for H in (3, 5, 10):
            f[f'fwd{H}'] = (np.exp(lc.shift(-H) - lc) - 1) * 100
        f['valid'] = d.p_dec.notna() & d.close.notna()
        f['stock'] = s; f['date'] = cal
        rows.append(f)
    panel = pd.concat(rows, ignore_index=True)
    return panel, D, intr


FEATURES = None


def feature_names(panel):
    drop = {'stock', 'date', 'valid', 'fwd3', 'fwd5', 'fwd10'}
    return [c for c in panel.columns if c not in drop]


class Path:
    """5-minute path of one symbol for exits at a target or a stop."""
    def __init__(self, intr, D):
        self.days = list(D.index[D.close.notna()])
        self.pos = {d: i for i, d in enumerate(self.days)}
        g = intr.groupby('date')
        self.bars = {d: (x.Open.values, x.High.values, x.Low.values, x.Close.values) for d, x in g}
        self.close = D.close

    def trade(self, day, side, H, target=None, stop=None):
        """Enter at the close of `day`; exit at target/stop (percent of entry, checked bar by bar from the
        next session; a bar that touches both counts as the stop) or at the close H sessions later."""
        i = self.pos[day]; entry = float(self.close[day])
        last = min(i + H, len(self.days) - 1)
        tp = entry * (1 + side * target / 100) if target else None
        sl = entry * (1 - side * stop / 100) if stop else None
        for j in range(i + 1, last + 1):
            d = self.days[j]; o, h, l, c = self.bars[d]
            if tp is None and sl is None:
                continue
            for k in range(len(o)):
                hit_sl = sl is not None and ((l[k] <= sl) if side > 0 else (h[k] >= sl))
                hit_tp = tp is not None and ((h[k] >= tp) if side > 0 else (l[k] <= tp))
                if hit_sl:
                    px = min(o[k], sl) if side > 0 else max(o[k], sl)     # a gap through the stop fills at the open
                    return d, px, 'stop'
                if hit_tp:
                    px = max(o[k], tp) if side > 0 else min(o[k], tp)
                    return d, px, 'target'
        d = self.days[last]
        return d, float(self.close[d]), 'time'


def run_trades(path, signal, H, target=None, stop=None, start=None, end=None, overlap=False):
    """signal: Series date -> +1 / -1 / 0. One position at a time unless overlap=True."""
    out = []; busy_until = None
    for day, side in signal.items():
        if side == 0 or np.isnan(side) or day not in path.pos:
            continue
        if (start is not None and day < pd.Timestamp(start)) or (end is not None and day > pd.Timestamp(end)):
            continue
        if not overlap and busy_until is not None and day <= busy_until:
            continue
        if path.pos[day] >= len(path.days) - 1:
            continue
        xd, px, why = path.trade(day, int(side), H, target, stop)
        entry = float(path.close[day])
        out.append(dict(entry_date=day, exit_date=xd, side=int(side), entry_price=entry, exit_price=px,
                        pnl=int(side) * (px - entry), ret=int(side) * (px / entry - 1) * 100, reason=why,
                        days=path.pos[xd] - path.pos[day]))
        busy_until = xd
    return pd.DataFrame(out)


def goal_stats(t, years):
    """G, WR and S for a trade table over the given calendar years (S per year, month average per trade > 1%)."""
    if len(t) == 0:
        return dict(n=0, G=np.nan, WR=np.nan, S=[0] * len(years), S_min=0, months_traded=[0] * len(years))
    t = t.copy(); t['y'] = t.entry_date.dt.year; t['m'] = t.entry_date.dt.strftime('%Y-%m')
    wins = (t.pnl > 0.005).sum(); losses = (t.pnl < -0.005).sum()
    S, MT = [], []
    for y in years:
        ma = t[t.y == y].groupby('m').ret.mean()
        S.append(int((ma > 1).sum())); MT.append(int(len(ma)))
    return dict(n=int(len(t)), G=float(t.ret.mean()), WR=float(100 * wins / max(1, wins + losses)),
                S=S, S_min=min(S), months_traded=MT, median=float(t.ret.median()),
                pf=float(t.ret[t.ret > 0].sum() / max(1e-9, -t.ret[t.ret < 0].sum())))
