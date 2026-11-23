"""
Stage 12 shared library: data loading, causal feature engineering and the
multi-day trade simulator used by every Stage 12 candidate.

Timing convention (no look-ahead)
---------------------------------
* A trading decision for day t is made at the START of the day's final
  5-minute bar. Every feature for day t therefore uses only 5-minute bars
  BEFORE the final bar of day t, plus daily values from days strictly
  before t. `p` is the close of the last bar before the final bar (the
  price known at decision time).
* Entries and exits are filled at the day's final close `c` (the close of
  the final 5-minute bar), i.e. one bar AFTER the decision.
* Rolling statistics (volatility, displacement scale, OU coefficient, ...)
  use days <= t-1 only.
"""
import numpy as np
import pandas as pd
from math import factorial

DATA = 'data/raw/CNQ_5min_20200727_to_20261118.csv'   # run from the repository root


def load_5min(path=DATA, end=None):
    df = pd.read_csv(path, parse_dates=['Datetime'])
    if end is not None:
        df = df[df.Datetime < end]
    df = df[['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']].copy()
    df['date'] = df.Datetime.dt.normalize()
    return df


def _perm_entropy(x, order=3):
    """Normalised permutation entropy (Bandt & Pompe 2002) of a 1-D series."""
    n = len(x) - order + 1
    if n < 10:
        return np.nan
    idx = np.lib.stride_tricks.sliding_window_view(x, order)
    pat = np.argsort(idx, axis=1, kind='stable')
    code = (pat * (order ** np.arange(order))).sum(1)
    _, cnt = np.unique(code, return_counts=True)
    pr = cnt / cnt.sum()
    return float(-(pr * np.log(pr)).sum() / np.log(factorial(order)))


def _levy_area(a, b):
    """Level-2 path-signature antisymmetric term (Levy area) of the 2-D path
    (a, b): 0.5 * sum(a_i * db_i - b_i * da_i), paths started at 0."""
    a = a - a[0]
    b = b - b[0]
    da = np.diff(a)
    db = np.diff(b)
    return float(0.5 * np.sum(a[:-1] * db - b[:-1] * da))


def build_daily(df5):
    """One row per trading day: true OHLCV + decision-time intraday features."""
    rows = []
    for date, g in df5.groupby('date', sort=True):
        o = g.Open.values; h = g.High.values; l = g.Low.values
        c = g.Close.values; v = g.Volume.values.astype(float)
        tm = g.Datetime.dt.hour.values * 60 + g.Datetime.dt.minute.values
        rec = dict(date=date, o=o[0], h=h.max(), l=l.min(), c=c[-1], v=v.sum(), nbars=len(g))
        if len(g) >= 20:
            # decision-time view: everything before the final bar
            cd = c[:-1]; hd = h[:-1]; ld = l[:-1]; vd = v[:-1]; td = tm[:-1]
            p = cd[-1]
            lr = np.diff(np.log(np.concatenate([[o[0]], cd])))
            rv = float(np.sum(lr ** 2))
            bv = float((np.pi / 2) * np.sum(np.abs(lr[1:]) * np.abs(lr[:-1])))
            hi = hd.max(); lo = ld.min()
            vw = float(np.sum(cd * vd) / vd.sum()) if vd.sum() > 0 else p
            last_hr = cd[td >= 15 * 60]
            first30 = cd[td < 10 * 60]
            path = np.log(cd / o[0])
            cumv = np.cumsum(vd) / max(vd.sum(), 1.0)
            tt = np.linspace(0, 1, len(cd))
            rec.update(
                p=p, hi_d=hi, lo_d=lo, rv=rv, bv=bv,
                jump=max(0.0, 1.0 - bv / rv) if rv > 0 else 0.0,
                clv=(p - lo) / (hi - lo) if hi > lo else 0.5,
                vwapdev=float(np.log(p / vw)),
                lasthr=float(np.log(p / last_hr[0])) if len(last_hr) > 1 else 0.0,
                first30=float(np.log(first30[-1] / o[0])) if len(first30) > 0 else 0.0,
                intraday=float(np.log(p / o[0])),
                pe=_perm_entropy(lr, 3),
                eff=float(abs(np.log(p / o[0])) / max(np.sum(np.abs(lr)), 1e-12)),
                levy_pv=_levy_area(path, cumv),      # price vs cumulative volume
                levy_pt=_levy_area(tt, path),        # time vs price (path convexity)
                upvol=float(vd[np.concatenate([[cd[0] >= o[0]], cd[1:] >= cd[:-1]])].sum() / max(vd.sum(), 1.0)),
            )
        rows.append(rec)
    d = pd.DataFrame(rows).set_index('date')
    return d


def kalman_llt(y, span):
    """Causal Kalman filter, local linear trend model (level + velocity).

    State noise is set from `span` so that the steady-state level gain is
    roughly that of an EMA with the same span (signal-to-noise fixed by
    design, not fitted to returns). Returns the ONE-STEP-AHEAD prediction of
    the level for each t (uses y up to t-1 only) and the filtered velocity
    available at t-1.
    """
    n = len(y)
    a = 2.0 / (span + 1.0)
    r = 1.0
    q_lvl = (a ** 2) / (1 - a) * r          # random-walk-plus-noise equivalent gain
    q_vel = q_lvl / (span ** 2)             # slow velocity
    F = np.array([[1.0, 1.0], [0.0, 1.0]])
    Q = np.diag([q_lvl, q_vel])
    H = np.array([1.0, 0.0])
    x = np.array([y[0], 0.0])
    P = np.eye(2) * 1.0
    pred = np.full(n, np.nan); vel = np.full(n, np.nan)
    for t in range(n):
        xp = F @ x
        Pp = F @ P @ F.T + Q
        pred[t] = xp[0]; vel[t] = xp[1]
        if np.isfinite(y[t]):
            S = H @ Pp @ H + r
            K = Pp @ H / S
            x = xp + K * (y[t] - xp[0])
            P = Pp - np.outer(K, H @ Pp)
        else:
            x, P = xp, Pp
    return pred, vel


def add_features(d, span=20):
    """Daily causal features. Uses p (decision-time price) for day t and
    true closes for days < t."""
    d = d.copy()
    lc = np.log(d.c)
    lp = np.log(d.p)
    r = lc.diff()                                   # close-to-close, known at t for t-1
    vol20 = r.rolling(20).std().shift(1)            # uses days <= t-1
    d['vol20'] = vol20
    prev_c = d.c.shift(1)
    tr = np.maximum(d.h - d.l, np.maximum((d.h - prev_c).abs(), (d.l - prev_c).abs()))
    d['atrp'] = (tr / prev_c).rolling(20).mean().shift(1)

    # --- control engineering: Kalman equilibrium and displacement ---------
    pred, vel = kalman_llt(lc.values, span)
    d['eq'] = pred
    x = lp - pred                                    # displacement at decision time
    xs = (lc - pred)                                 # past displacements (close based)
    sx = xs.rolling(60, min_periods=30).std().shift(1)
    d['x'] = x
    d['z'] = x / sx
    d['velz'] = pd.Series(vel, index=d.index) / vol20
    # --- stochastic calculus: OU speed, half-life, expected reversion ------
    x0 = xs.shift(1); x1 = xs
    cov = (x0 * x1).rolling(60, min_periods=30).mean() - x0.rolling(60, min_periods=30).mean() * x1.rolling(60, min_periods=30).mean()
    var = x0.rolling(60, min_periods=30).var()
    phi = (cov / var).shift(1).clip(0.0, 0.99)
    d['phi'] = phi
    d['ou5'] = -x * (1 - phi ** 5)
    d['ou10'] = -x * (1 - phi ** 10)
    # --- classical mechanics analogue: energy of the stretch --------------
    d['pe_spring'] = 0.5 * d.z ** 2 * np.sign(-d.z)   # signed potential energy
    d['dz'] = d.z - (xs / sx).shift(1)                # velocity of the displacement
    # --- standardised multi-horizon returns --------------------------------
    for k in (1, 2, 3, 5, 10, 20):
        d[f'r{k}'] = (lp - lc.shift(k)) / (vol20 * np.sqrt(k))
    # --- overnight / intraday tug of war -----------------------------------
    on = np.log(d.o / prev_c)
    intr = np.log(d.c / d.o)
    d['on'] = on / vol20
    d['on5'] = (on.rolling(5).sum()) / vol20
    d['id5'] = (intr.shift(1).rolling(4).sum() + d.intraday) / vol20
    d['intraday_z'] = d.intraday / vol20
    d['lasthr_z'] = d.lasthr / vol20
    d['first30_z'] = d.first30 / vol20
    d['vwapdev_z'] = d.vwapdev / vol20
    # --- volatility physics: realised variance, HAR ratios, jumps ----------
    rvd = np.sqrt(d.rv)
    d['rv_rel'] = rvd / rvd.rolling(20).mean().shift(1)
    d['rv5_20'] = rvd.rolling(5).mean() / rvd.rolling(20).mean()
    d['jump5'] = d.jump.rolling(5).mean()
    # --- fractal / information measures ------------------------------------
    d['pe5'] = d.pe.rolling(5).mean()
    d['eff5'] = d.eff.rolling(5).mean()
    r5 = lc.diff(5)
    vr5 = (r5.rolling(60, min_periods=40).var() / (5 * r.rolling(60, min_periods=40).var())).shift(1)
    d['hurst'] = 0.5 + np.log(vr5.clip(0.05, 20)) / (2 * np.log(5))
    # --- rough-path signature terms ----------------------------------------
    d['levy_pv_z'] = d.levy_pv / vol20
    d['levy_pt_z'] = d.levy_pt / vol20
    # --- volume / range context --------------------------------------------
    lv = np.log(d.v.replace(0, np.nan))
    d['volz'] = (lv - lv.rolling(20).mean().shift(1)) / lv.rolling(20).std().shift(1)
    hh20 = d.h.rolling(20).max().shift(1)
    ll20 = d.l.rolling(20).min().shift(1)
    d['dd20'] = np.log(d.p / np.maximum(hh20, d.hi_d)) / vol20
    d['pos20'] = (d.p - np.minimum(ll20, d.lo_d)) / (np.maximum(hh20, d.hi_d) - np.minimum(ll20, d.lo_d))
    d['sma50'] = np.log(d.p / d.c.rolling(50, min_periods=30).mean().shift(1)) / vol20
    return d


FEATURES = ['z', 'velz', 'phi', 'ou5', 'pe_spring', 'dz', 'r1', 'r2', 'r3', 'r5', 'r10', 'r20',
            'on', 'on5', 'id5', 'intraday_z', 'lasthr_z', 'first30_z', 'vwapdev_z', 'clv',
            'rv_rel', 'rv5_20', 'jump5', 'pe5', 'eff5', 'hurst', 'levy_pv_z', 'levy_pt_z',
            'volz', 'dd20', 'pos20', 'sma50', 'upvol']


def simulate(d, signal, H=5, z_exit=None, stop_atr=None, side=1):
    """One position at a time. Enter at close c of the signal day; then on each
    later day decide at decision time (price p) whether to exit at that
    day's close. Exit reasons: displacement reverted (z >= z_exit for longs),
    close-based stop (p <= entry*(1-stop_atr*atrp)), or the H-day time limit.
    Returns a DataFrame of trades (gross % on entry price)."""
    idx = d.index
    c = d.c.values; p = d.p.values; z = d.z.values; atr = d.atrp.values
    sig = np.asarray(signal, dtype=bool)
    trades = []
    i = 0; n = len(d)
    while i < n - 1:
        if not sig[i] or not np.isfinite(c[i]):
            i += 1; continue
        entry = c[i]; a = atr[i]
        j = i + 1; reason = 'time'
        while True:
            held = j - i
            if z_exit is not None and np.isfinite(z[j]) and side * z[j] >= z_exit:
                reason = 'revert'; break
            if stop_atr is not None and np.isfinite(a) and side * (p[j] / entry - 1) <= -stop_atr * a:
                reason = 'stop'; break
            if held >= H or j == n - 1:
                reason = 'time' if held >= H else 'eod'; break
            j += 1
        ret = side * (c[j] / entry - 1) * 100
        trades.append(dict(entry_date=idx[i], exit_date=idx[j], entry=entry, exit=c[j],
                           days=j - i, ret=ret, reason=reason, side=side))
        i = j + 1          # earliest re-entry: the day after the exit
    return pd.DataFrame(trades)


def stats(tr, cost_cents=None):
    if tr is None or len(tr) == 0:
        return dict(n=0, avg=np.nan, win=np.nan, pf=np.nan, days=np.nan, med=np.nan)
    r = tr.ret.values
    w = r[r > 0].sum(); l = -r[r < 0].sum()
    out = dict(n=int(len(r)), avg=float(r.mean()), med=float(np.median(r)),
               win=float((r > 0).mean() * 100), pf=float(w / l) if l > 0 else float('inf'),
               days=float(tr.days.mean()), best=float(r.max()), worst=float(r.min()),
               total=float(r.sum()))
    if cost_cents is not None:
        out['avg_net'] = float((r - cost_cents / tr.entry.values).mean())
    return out


def baseline_drift(d, H):
    """Average H-day close-to-close % return over every possible entry day in d
    (what a random-entry, same-holding-period long would have earned)."""
    f = (d.c.shift(-H) / d.c - 1) * 100
    return float(f.mean())
