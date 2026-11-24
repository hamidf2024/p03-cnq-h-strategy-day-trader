"""
Stage 14 library: new information for the CNQ models.

Eighteen more symbols from the same source as the Stage 13 data (5-minute consolidated-feed bars), turned into
daily features that are known at the decision time (15:50) of each day:

    oil curve      USL (12-month oil fund) against USO (front-month): the slope of the oil futures curve
    Brent-WTI      BNO against USO
    natural gas    UNG
    refining       VLO, MPC, PSX against the producers' fund XOP: the refining margin
    oil services   OIH against XOP
    pipelines      ENB, TRP
    currency       FXC (Canadian dollar), UUP (US dollar)
    markets        SPY, EWC (Canada), VIXY (volatility), TLT (long bonds), HYG (high-yield bonds), GLD (gold)

USL and FXC trade thinly (about a third of the 5-minute bars exist), so they are used as daily prices only:
the last trade at or before 15:50, carried forward at most three sessions.

The Stage 13 panel (57 features per stock and day) is extended with these; everything is causal, and the
test years are removed at load when S13_CUTOFF is set.
"""
import glob
import os
import numpy as np
import pandas as pd
import s13_lib as L

LIQUID = ['BNO', 'UNG', 'VLO', 'MPC', 'PSX', 'XOP', 'OIH', 'ENB', 'TRP', 'UUP', 'EWC', 'SPY', 'VIXY', 'TLT', 'HYG', 'GLD']
THIN = ['USL', 'FXC']


def thin_daily(sym, cal):
    f = sorted(glob.glob(f'{L.DATA}/{sym}_5min_sip_*.csv'))[-1]
    df = pd.read_csv(f, usecols=['Datetime', 'Close'], parse_dates=['Datetime'])
    df['date'] = df.Datetime.dt.normalize()
    df = df[df.date <= os.environ.get('S13_CUTOFF', L.LAST_FULL_DAY)]
    tm = df.Datetime.dt.hour * 60 + df.Datetime.dt.minute
    p = df[tm <= 950].groupby('date').Close.last()
    return p.reindex(cal).ffill(limit=3)


def macro_frame(cal, D13):
    """Daily log prices at decision time for the new symbols, plus the Stage 13 ones needed for spreads."""
    lp = {}; extra = {}
    for s in LIQUID:
        d = L.daily(L.load_5min(s)).reindex(cal); lp[s] = np.log(d.p_dec); extra[s] = d
    for s in THIN:
        lp[s] = np.log(thin_daily(s, cal))
    for s in ('USO', 'XLE'):
        lp[s] = np.log(D13[s].p_dec.reindex(cal))
    return pd.DataFrame(lp), extra


def z(s, n):
    return (s - s.rolling(n).mean()) / s.rolling(n).std()


def macro_features(lp, extra):
    f = pd.DataFrame(index=lp.index)
    curve = lp.USL - lp.USO; brent = lp.BNO - lp.USO
    f['curve_z60'] = z(curve, 60); f['curve_d5'] = curve.diff(5); f['curve_d20'] = curve.diff(20)
    f['brent_z60'] = z(brent, 60); f['brent_d5'] = brent.diff(5); f['brent_d20'] = brent.diff(20)
    for k in (1, 5, 20):
        f[f'ung{k}'] = lp.UNG.diff(k)
    ref = lp[['VLO', 'MPC', 'PSX']].mean(axis=1)
    for k in (5, 20):
        f[f'crack{k}'] = ref.diff(k) - lp.XOP.diff(k)
        f[f'svc{k}'] = lp.OIH.diff(k) - lp.XOP.diff(k)
        f[f'xop{k}'] = lp.XOP.diff(k)
        f[f'pipe{k}'] = lp[['ENB', 'TRP']].mean(axis=1).diff(k)
        f[f'cad{k}'] = lp.FXC.diff(k); f[f'usd{k}'] = lp.UUP.diff(k)
        f[f'tlt{k}'] = lp.TLT.diff(k); f[f'hyg{k}'] = lp.HYG.diff(k); f[f'credit{k}'] = lp.HYG.diff(k) - lp.TLT.diff(k)
        f[f'gld{k}'] = lp.GLD.diff(k)
    for k in (1, 5, 20):
        f[f'spy{k}'] = lp.SPY.diff(k); f[f'ewc{k}'] = lp.EWC.diff(k); f[f'vix{k}'] = lp.VIXY.diff(k)
    f['spy_z20'] = z(lp.SPY, 20); f['vix_z20'] = z(lp.VIXY, 20); f['vix_z60'] = z(lp.VIXY, 60)
    f['spy_intraday'] = np.log(extra['SPY'].p_dec / extra['SPY'].open)
    f['spy_rv_ratio'] = extra['SPY'].rv.rolling(5).mean() / extra['SPY'].rv.rolling(20).mean()
    f['xop_z20'] = z(lp.XOP, 20)
    return f


def build_panel14(panel, D13):
    """Stage 13 panel plus the macro features (same for every stock on a day) and a few stock-against-market ones."""
    cal = D13['USO'].index
    lp, extra = macro_frame(cal, D13)
    mf = macro_features(lp, extra)
    r_spy = lp.SPY.diff()
    parts = []
    for s in L.STOCKS:
        p = panel[panel.stock == s].set_index('date').copy()
        ls = np.log(D13[s].p_dec.reindex(cal)); r = ls.diff()
        g = mf.reindex(p.index).copy()
        b = r.rolling(60).cov(r_spy) / r_spy.rolling(60).var()
        res = r - b.shift(1) * r_spy
        for k in (5, 20):
            g[f'mkt_res{k}'] = (res.rolling(k).sum() / (res.rolling(60).std() * np.sqrt(k))).reindex(p.index)
            g[f'rel_xop{k}'] = (ls.diff(k) - lp.XOP.diff(k)).reindex(p.index)
            g[f'rel_ewc{k}'] = (ls.diff(k) - lp.EWC.diff(k)).reindex(p.index)
        g['mkt_beta'] = b.reindex(p.index)
        lc = np.log(D13[s].close.reindex(cal))
        g['fwd20'] = ((np.exp(lc.shift(-20) - lc) - 1) * 100).reindex(p.index)
        parts.append(pd.concat([p, g], axis=1).reset_index())
    out = pd.concat(parts, ignore_index=True)
    new = [c for c in out.columns if c not in panel.columns and c != 'fwd20']
    return out, new
