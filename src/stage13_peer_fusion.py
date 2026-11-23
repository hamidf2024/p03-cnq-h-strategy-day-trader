"""
Stage 13: peer-and-oil models for CNQ, aimed at the three goal ladders.

Four rounds, all designed and written down before any of them was run on
2024-2026 (docs/12_Stage13_Peer_Fusion_Research.md):

  R1  Peer-Fusion GBM      one gradient-boosted model trained on all six oil stocks at once
  R2  Peer-and-oil spring  rule: CNQ stretched away from its peers and from oil, and turning back
  R3  Fusion ensemble      R1's model + a ridge model + a cross-asset transformer, ranks averaged
  R4  Goal-shaped exits    the better of R1/R3 with a profit target and a stop

Protocol (unchanged from Stages 10-12): walk-forward on 2020-2023 (validation
years 2021, 2022, 2023, labels purged at each boundary), freeze, then one run
on 2024-01-02..2026-11-18.

    python3 src/stage13_peer_fusion.py walkforward   # selects and freezes; never touches 2024-2026
    python3 src/stage13_peer_fusion.py blind [artefact]    # one run per round, ever; rounds already in the run log are skipped
    python3 src/stage13_peer_fusion.py verify [artefact]   # re-runs the identical frozen artefact and compares

Entries use the model's own recent history as the yardstick: a day is taken
when its prediction ranks in the top (or bottom) part of the previous 120
out-of-sample predictions. That keeps the number of trades steady from year to
year, which the steadiness goal needs.
"""
import hashlib, json, os, pickle, sys, warnings
import numpy as np, pandas as pd
import lightgbm as lgb
from sklearn.linear_model import Ridge
import s13_lib as L

warnings.filterwarnings('ignore')
RES = os.environ.get('S13_OUT', 'results/experiments')
VAL_YEARS = [2021, 2022, 2023]
BLIND_YEARS = [2024, 2025, 2026]
HS = (5, 10)
RANK_WIN, RANK_MIN = 120, 40
SEEDS = (0, 1, 2, 3, 4)
GBM = dict(n_estimators=300, learning_rate=0.03, num_leaves=8, max_depth=3, min_child_samples=40, subsample=0.7,
           subsample_freq=1, colsample_bytree=0.5, reg_lambda=5.0, verbose=-1, n_jobs=2)
MIN_TRADES_PER_YEAR = 6


# ----------------------------------------------------------------- data
def get_panel():
    cut = os.environ.get('S13_CUTOFF', '')
    f = f'{RES}/stage13_panel_cache{"_to_" + cut if cut else ""}.pkl'      # holds prices: local only
    if os.path.exists(f):
        return pickle.load(open(f, 'rb'))
    out = L.build_panel(); pickle.dump(out, open(f, 'wb')); return out


def trailing_rank(s, win=RANK_WIN, minp=RANK_MIN):
    """Share of the previous `win` values that are below today's value (today excluded). Causal."""
    v = s.values; out = np.full(len(v), np.nan)
    for i in range(len(v)):
        past = v[max(0, i - win):i]; past = past[~np.isnan(past)]
        if len(past) >= minp and not np.isnan(v[i]):
            out[i] = (past < v[i]).mean()
    return pd.Series(out, index=s.index)


def label(panel, H, mu):
    y = (panel[f'fwd{H}'] - mu) / (panel.vol20 * np.sqrt(H) * 100)
    return y.clip(-4, 4)


def train_rows(panel, cal, cutoff_day, H):
    """Rows whose label ends before cutoff_day (purge of H sessions)."""
    pos = cal.get_indexer([cutoff_day])[0]
    last = cal[pos - H - 1]
    return panel.valid & panel[f'fwd{H}'].notna() & panel.vol20.notna() & (panel.date <= last) & panel.r60.notna()


# ----------------------------------------------------------------- models
def fit_gbm(X, y):
    return [lgb.LGBMRegressor(random_state=s, **GBM).fit(X, y) for s in SEEDS]


def fit_ridge(X, y):
    mu, sd = X.mean(), X.std().replace(0, 1)
    Z = ((X - mu) / sd).clip(-5, 5).fillna(0)
    return (Ridge(alpha=300.0).fit(Z, y), mu, sd)


def pred_ridge(m, X):
    r, mu, sd = m
    return r.predict(((X - mu) / sd).clip(-5, 5).fillna(0))


TOK = ['r1', 'overnight', 'intraday', 'rv_ratio', 'volz']
SEQ = 40


def token_tensor(panel, D, cal):
    """(days, 8 assets x 5 features): the six stocks from the panel, the oil and sector funds from their dailies."""
    cols = []
    for s in L.STOCKS:
        p = panel[panel.stock == s].set_index('date').reindex(cal)
        cols.append(p[TOK].values)
    for s in L.AUX:
        d = D[s]; lp = np.log(d.p_dec)
        a = pd.DataFrame({'r1': lp.diff(), 'overnight': np.log(d.open / d.close.shift(1)), 'intraday': np.log(d.p_dec / d.open),
                          'rv_ratio': d.rv.rolling(5).mean() / d.rv.rolling(20).mean(),
                          'volz': L.z(np.log(d.vol.replace(0, np.nan)), 20)}).reindex(cal)
        cols.append(a[TOK].values)
    return np.concatenate(cols, axis=1)


def fit_transformer(T, Y, idx, seeds=(0, 1, 2)):
    """T: token matrix (days x F); Y: (days x 6) standardised labels; idx: training day positions."""
    import torch, torch.nn as nn
    torch.set_num_threads(2)
    mu = np.nanmean(T[idx], axis=0); sd = np.nanstd(T[idx], axis=0); sd[sd == 0] = 1
    Z = np.nan_to_num(np.clip((T - mu) / sd, -5, 5))
    idx = np.array([i for i in idx if i >= SEQ]); models = []
    Xs = torch.tensor(np.stack([Z[i - SEQ + 1:i + 1] for i in idx]), dtype=torch.float32)
    Yt = torch.tensor(np.nan_to_num(Y[idx]), dtype=torch.float32); Mk = torch.tensor(~np.isnan(Y[idx]), dtype=torch.float32)

    class Net(nn.Module):
        def __init__(s, F):
            super().__init__()
            s.inp = nn.Linear(F, 32); s.pos = nn.Parameter(torch.zeros(SEQ, 32))
            enc = nn.TransformerEncoderLayer(32, 4, 64, dropout=0.2, batch_first=True)
            s.enc = nn.TransformerEncoder(enc, 2); s.out = nn.Linear(32, 6)

        def forward(s, x):
            return s.out(s.enc(s.inp(x) + s.pos)[:, -1])
    for seed in seeds:
        torch.manual_seed(seed); net = Net(Z.shape[1]); opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-2)
        n = len(idx)
        for ep in range(30):
            perm = torch.randperm(n); net.train()
            for b in range(0, n, 64):
                j = perm[b:b + 64]; opt.zero_grad()
                loss = (nn.functional.huber_loss(net(Xs[j]), Yt[j], reduction='none') * Mk[j]).sum() / Mk[j].sum().clamp(min=1)
                loss.backward(); opt.step()
        net.eval(); models.append(net.state_dict())
    return dict(states=models, mu=mu, sd=sd, F=Z.shape[1], Net=None)


def pred_transformer(m, T, days_pos):
    import torch, torch.nn as nn
    Z = np.nan_to_num(np.clip((T - m['mu']) / m['sd'], -5, 5))

    class Net(nn.Module):
        def __init__(s, F):
            super().__init__()
            s.inp = nn.Linear(F, 32); s.pos = nn.Parameter(torch.zeros(SEQ, 32))
            enc = nn.TransformerEncoderLayer(32, 4, 64, dropout=0.2, batch_first=True)
            s.enc = nn.TransformerEncoder(enc, 2); s.out = nn.Linear(32, 6)

        def forward(s, x):
            return s.out(s.enc(s.inp(x) + s.pos)[:, -1])
    ok = [i for i in days_pos if i >= SEQ]
    X = torch.tensor(np.stack([Z[i - SEQ + 1:i + 1] for i in ok]), dtype=torch.float32)
    out = np.zeros((len(ok), 6))
    for st in m['states']:
        net = Net(m['F']); net.load_state_dict(st); net.eval()
        with torch.no_grad():
            out += net(X).numpy() / len(m['states'])
    return ok, out


def fit_all(panel, D, cal, T, cutoff_day, H, feats):
    """Fits the three models on rows whose labels end before cutoff_day."""
    tr = train_rows(panel, cal, cutoff_day, H)
    mu = float(panel.loc[tr, f'fwd{H}'].mean())
    y = label(panel, H, mu)
    X = panel.loc[tr, feats]
    Ymat = np.column_stack([y[panel.stock == s].where(tr[panel.stock == s]).values for s in L.STOCKS])
    last = panel.loc[tr, 'date'].max(); idx = np.where(cal <= last)[0]
    return dict(H=H, mu=mu, gbm=fit_gbm(X, y[tr]), ridge=fit_ridge(X, y[tr]), tf=fit_transformer(T, Ymat, idx), train_last=str(last.date()))


def predict_cnq(m, panel, cal, T, days, feats):
    """CNQ predictions of the three models for the given days."""
    c = panel[(panel.stock == 'CNQ')].set_index('date').reindex(days)
    X = c[feats]
    out = pd.DataFrame(index=days)
    out['gbm'] = np.mean([g.predict(X) for g in m['gbm']], axis=0)
    out['ridge'] = pred_ridge(m['ridge'], X)
    pos = cal.get_indexer(days); ok, p = pred_transformer(m['tf'], T, pos)
    out['tf'] = pd.Series(p[:, 0], index=cal[ok]).reindex(days)          # column 0 = CNQ
    out.loc[~c.valid.fillna(False).values] = np.nan
    return out


# ----------------------------------------------------------------- signals
def score_series(preds, which):
    """Trailing-rank score in [0,1] from one model or from the average of the three models' ranks."""
    if which == 'gbm':
        return trailing_rank(preds['gbm'])
    r = pd.concat([trailing_rank(preds[k]) for k in ('gbm', 'ridge', 'tf')], axis=1)
    return trailing_rank(r.mean(axis=1, skipna=False))


def sig_from_score(score, side, q=0.85):
    s = pd.Series(0.0, index=score.index)
    s[score >= q] = 1
    if side == 'both':
        s[score <= 1 - q] = -1
    return s


def spring_signal(cnq, k, side):
    z = (cnq.peer_res10 + cnq.oil_res10) / 2
    lo = z.rolling(3).min(); hi = z.rolling(3).max()
    s = pd.Series(0.0, index=cnq.index)
    s[(lo <= -k) & (z > z.shift(1)) & (z < 0)] = 1                        # stretched below, turning back up
    if side == 'both':
        s[(hi >= k) & (z < z.shift(1)) & (z > 0)] = -1
    s[~cnq.valid] = 0
    return s


# ----------------------------------------------------------------- evaluation
class Bench:
    """Average result of entering on every day of a year with the same exit rule (the 'no skill' line)."""
    def __init__(self, path, cnq):
        self.path, self.cnq, self.cache = path, cnq, {}

    def get(self, year, side, H, target, stop):
        key = (year, side, H, target, stop)
        if key not in self.cache:
            days = [d for d in self.cnq.index[self.cnq.valid] if d.year == year and self.path.pos.get(d, 10 ** 9) < len(self.path.days) - 1]
            if target is None and stop is None:
                v = side * self.cnq.loc[days, f'fwd{H}'].dropna() if H in (3, 5, 10) else None
                self.cache[key] = float(v.mean())
            else:
                r = []
                for d in days:
                    xd, px, _ = self.path.trade(d, side, H, target, stop); e = float(self.path.close[d])
                    r.append(side * (px / e - 1) * 100)
                self.cache[key] = float(np.mean(r))
        return self.cache[key]


def evaluate(path, bench, sig, H, target, stop, years, start=None, end=None, overlap=False):
    t = L.run_trades(path, sig, H, target, stop, start=start or f'{years[0]}-01-01', end=end or f'{years[-1]}-12-31', overlap=overlap)
    per_year = {}
    for y in years:
        ty = t[t.entry_date.dt.year == y] if len(t) else t
        if len(ty):
            ex = float(np.mean([r - bench.get(y, s, H, target, stop) for r, s in zip(ty.ret, ty.side)]))
            ma = ty.groupby(ty.entry_date.dt.strftime('%Y-%m')).ret.mean()
            per_year[y] = dict(n=int(len(ty)), G=round(float(ty.ret.mean()), 3), excess=round(ex, 3),
                               WR=round(float((ty.pnl > 0.005).sum() / max(1, (ty.pnl.abs() > 0.005).sum()) * 100), 1),
                               S=int((ma > 1).sum()), months_traded=int(len(ma)), shorts=int((ty.side < 0).sum()))
        else:
            per_year[y] = dict(n=0, G=None, excess=None, WR=None, S=0, months_traded=0, shorts=0)
    g = L.goal_stats(t, years)
    exs = [per_year[y]['excess'] for y in years if per_year[y]['n']]
    allex = float(np.mean([r - bench.get(d.year, s, H, target, stop) for r, s, d in zip(t.ret, t.side, t.entry_date)])) if len(t) else None
    return t, dict(n=g['n'], G=None if g['n'] == 0 else round(g['G'], 3), WR=None if g['n'] == 0 else round(g['WR'], 1), S=g['S'],
                   excess=None if allex is None else round(allex, 3), worst_year_excess=round(min(exs), 3) if len(exs) == len(years) else None,
                   min_trades_year=min(per_year[y]['n'] for y in years), per_year=per_year)


def choose(results):
    """Pre-registered rule: among settings with at least MIN_TRADES_PER_YEAR trades in every validation year,
    the one with the best worst-year excess over the no-skill line."""
    ok = {k: v for k, v in results.items() if v['min_trades_year'] >= MIN_TRADES_PER_YEAR and v['worst_year_excess'] is not None}
    pool = ok if ok else {k: v for k, v in results.items() if v['n'] >= 12 and v['excess'] is not None}
    key = (lambda k: pool[k]['worst_year_excess']) if ok else (lambda k: pool[k]['excess'])
    best = max(pool, key=key)
    return best, bool(ok)


def strict_view(results, years):
    """Pick the setting on the earlier validation years only, score it on the next one."""
    out = []
    for i in range(1, len(years)):
        past = years[:i]; y = years[i]
        cand = {k: np.mean([v['per_year'][p]['excess'] for p in past]) for k, v in results.items()
                if all(v['per_year'][p]['n'] >= 4 for p in past)}
        if not cand:
            continue
        k = max(cand, key=cand.get); py = results[k]['per_year'][y]
        if py['n']:
            out.append(dict(year=y, picked=k, n=py['n'], G=py['G'], excess=py['excess']))
    return out


# ----------------------------------------------------------------- main steps
def setup():
    panel, D, intr = get_panel()
    cal = D['USO'].index
    feats = L.feature_names(panel)
    cnq = panel[panel.stock == 'CNQ'].set_index('date')
    path = L.Path(intr['CNQ'], D['CNQ']); bench = Bench(path, cnq)
    T = token_tensor(panel, D, cal)
    return panel, D, cal, feats, cnq, path, bench, T


def walkforward():
    panel, D, cal, feats, cnq, path, bench, T = setup()
    assert cal.max() >= pd.Timestamp('2024-01-02')
    train_days = cal[cal <= L.TRAIN_END]
    VAL_END = str(train_days[-11].date())            # last validation entry: every exit falls inside 2023
    out = {'protocol': 'stage13 v1', 'validation_years': VAL_YEARS, 'rounds': {}}
    # out-of-fold predictions for 2021-2023, per horizon
    oof = {}
    for H in HS:
        parts = []
        for y in VAL_YEARS:
            days = train_days[train_days.year == y]
            m = fit_all(panel, D, cal, T, days[0], H, feats)
            parts.append(predict_cnq(m, panel, cal, T, days, feats))
            print(f'fold {y} H={H} trained to {m["train_last"]}', flush=True)
        oof[H] = pd.concat(parts)
        ic = {k: round(float(oof[H][k].corr(cnq[f'fwd{H}'].reindex(oof[H].index), method='spearman')), 3) for k in ('gbm', 'ridge', 'tf')}
        out.setdefault('oof_rank_ic', {})[H] = ic; print('rank IC', H, ic, flush=True)
    grids = {
        'R1_peer_fusion_gbm': [dict(src='gbm', H=H, side=s, target=None, stop=None) for H in HS for s in ('long', 'both')],
        'R2_peer_oil_spring': [dict(src='spring', H=H, side=s, k=k, target=None, stop=None) for H in HS for s in ('long', 'both') for k in (1.0, 1.5)],
        'R3_fusion_ensemble': [dict(src='ens', H=H, side=s, target=None, stop=None) for H in HS for s in ('long', 'both')],
    }
    chosen = {}

    def signal_for(cfg, preds_by_H):
        if cfg['src'] == 'spring':
            return spring_signal(cnq, cfg['k'], cfg['side'])
        return sig_from_score(score_series(preds_by_H[cfg['H']], cfg['src']), cfg['side'])

    def run_round(name, grid):
        res = {}
        for cfg in grid:
            sig = signal_for(cfg, oof).reindex(train_days).fillna(0)
            _, st = evaluate(path, bench, sig, cfg['H'], cfg['target'], cfg['stop'], VAL_YEARS, end=VAL_END)
            res[json.dumps(cfg, sort_keys=True)] = st
        best, clean = choose(res)
        out['rounds'][name] = dict(settings=res, chosen=json.loads(best), chosen_by_main_rule=clean, chosen_stats=res[best],
                                   strict_view=strict_view(res, VAL_YEARS))
        chosen[name] = json.loads(best)
        print(name, 'chosen', best, {k: res[best][k] for k in ('n', 'G', 'WR', 'S', 'excess', 'worst_year_excess')}, flush=True)
    for name, grid in grids.items():
        run_round(name, grid)
    # R4: the better of R1 / R3 (by worst-year excess), with a target and a stop, 10-session limit
    a, b = out['rounds']['R1_peer_fusion_gbm']['chosen_stats'], out['rounds']['R3_fusion_ensemble']['chosen_stats']
    base = chosen['R1_peer_fusion_gbm'] if (a['worst_year_excess'] or -9) >= (b['worst_year_excess'] or -9) else chosen['R3_fusion_ensemble']
    grid4 = [dict(src=base['src'], H=base['H'], side=base['side'], hold=10, target=t, stop=s) for t in (3.0, 5.0) for s in (3.0, 5.0, None)]
    res = {}
    for cfg in grid4:
        sig = signal_for(cfg, oof).reindex(train_days).fillna(0)
        _, st = evaluate(path, bench, sig, cfg['hold'], cfg['target'], cfg['stop'], VAL_YEARS, end=VAL_END)
        res[json.dumps(cfg, sort_keys=True)] = st
    best, clean = choose(res)
    out['rounds']['R4_goal_shaped_exits'] = dict(settings=res, chosen=json.loads(best), chosen_by_main_rule=clean, chosen_stats=res[best],
                                                 strict_view=strict_view(res, VAL_YEARS), built_on=base)
    chosen['R4_goal_shaped_exits'] = json.loads(best)
    print('R4 chosen', best, {k: res[best][k] for k in ('n', 'G', 'WR', 'S', 'excess', 'worst_year_excess')}, flush=True)
    # final models on all of 2020-2023 (labels purged at the end of 2023), one per horizon in use
    first_blind = cal[cal >= L.BLIND_START][0]
    finals = {H: fit_all(panel, D, cal, T, first_blind, H, feats) for H in sorted({c['H'] for c in chosen.values() if c['src'] != 'spring'})}
    frozen = dict(chosen=chosen, finals=finals, oof={H: oof[H] for H in finals}, feats=feats, gbm_params=GBM)
    blob = pickle.dumps(frozen); open(f'{RES}/stage13_frozen.pkl', 'wb').write(blob)
    out['frozen_sha256'] = hashlib.sha256(blob).hexdigest()
    json.dump(out, open(f'{RES}/stage13_walkforward_results.json', 'w'), indent=1, default=str)
    print('frozen', out['frozen_sha256'][:16], flush=True)


def signal_from_cfg(cfg, cnq, preds):
    if cfg['src'] == 'spring':
        return spring_signal(cnq, cfg['k'], cfg['side'])
    if cfg['src'] == 'always':
        return cnq.valid.astype(float)
    if cfg.get('monthly'):                       # one trade a month: the first day whose score clears the bar
        sc = score_series(preds[cfg['H']], cfg['src']); out = pd.Series(0.0, index=sc.index); done = set()
        for d, v in sc.items():
            m = (d.year, d.month) if cfg.get('per_month', 1) == 1 else (d.year, d.month, int(d.day > 15))   # two a month: one per half
            if m not in done and not np.isnan(v) and v >= cfg['q']:
                out[d] = 1; done.add(m)
        return out
    return sig_from_score(score_series(preds[cfg['H']], cfg['src']), cfg['side'], cfg.get('q', 0.85))


def blind(artefact, verify=False):
    """Runs every round in the frozen artefact that has not been run before. One run per round, ever."""
    logf = f'{RES}/stage13_BLIND_RUN_LOG.json'; resf = f'{RES}/stage13_blind_results.json'
    log = json.load(open(logf)) if os.path.exists(logf) else {}
    allres = json.load(open(resf)) if os.path.exists(resf) else {}
    blob = open(f'{RES}/{artefact}', 'rb').read(); sha = hashlib.sha256(blob).hexdigest()
    frozen = pickle.loads(blob)
    assert sha == frozen.get('expect_sha', sha)
    todo = [r for r in frozen['chosen'] if (r in log) == verify]
    if not todo:
        sys.exit('Nothing to do: every round in this artefact has already had its one blind run (use "verify" to reproduce).')
    panel, D, cal, feats, cnq, path, bench, T = setup()
    assert feats == frozen['feats']
    days = cal[(cal >= L.BLIND_START)]
    preds = {H: pd.concat([frozen['oof'][H], predict_cnq(m, panel, cal, T, days, feats)]) for H, m in frozen['finals'].items()}
    trades = []
    for name in todo:
        cfg = frozen['chosen'][name]
        sig = signal_from_cfg(cfg, cnq, preds).reindex(cal).fillna(0)
        t, st = evaluate(path, bench, sig, cfg.get('hold', cfg['H']), cfg['target'], cfg['stop'], BLIND_YEARS, start=L.BLIND_START, end=L.BLIND_END,
                         overlap=cfg.get('overlap', False))
        st['setting'] = cfg
        if len(t):
            rng = np.random.default_rng(0); r = t.ret.values
            bs = [rng.choice(r, len(r)).mean() for _ in range(5000)]
            st['G_ci95'] = [round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)]
            st['median'] = round(float(t.ret.median()), 3); st['worst_trade'] = round(float(r.min()), 2); st['best_trade'] = round(float(r.max()), 2)
            st['G_without_top2'] = round(float(np.sort(r)[:-2].mean()), 3) if len(r) > 4 else None
            st['net_after_1c'] = round(float(((t.pnl - 0.01) / t.entry_price * 100).mean()), 3)
            st['avg_days_held'] = round(float(t.days.mean()), 1); st['exits'] = t.reason.value_counts().to_dict()
            eq = (t.ret).cumsum(); st['max_drawdown_sum_pct'] = round(float((eq - eq.cummax()).min()), 2)
            t.insert(0, 'model', name); trades.append(t)
        payload = json.dumps(st, sort_keys=True, default=str)
        if verify:
            print('VERIFY', name, 'identical' if json.dumps(allres[name], sort_keys=True, default=str) == payload else 'DIFFERENT'); continue
        allres[name] = json.loads(payload)
        log[name] = dict(frozen_artefact=artefact, frozen_sha256=sha, ran_on=str(pd.Timestamp.now()), blind_window=[L.BLIND_START, L.BLIND_END],
                         blind_look_number=len(log) + 1, result_sha256=hashlib.sha256(payload.encode()).hexdigest())
        print(name, {k: st[k] for k in ('n', 'G', 'WR', 'S', 'excess')}, flush=True)
    if verify or not trades:
        return
    json.dump(allres, open(resf, 'w'), indent=1); json.dump(log, open(logf, 'w'), indent=1)
    allt = pd.concat(trades)
    pub, loc = f'{RES}/stage13_blind_trades.csv', f'{RES}/stage13_blind_trades_LOCAL_ONLY.csv'
    a = allt.drop(columns=['entry_price', 'exit_price', 'pnl'])                                   # published copy: no prices
    b = allt.rename(columns={'model': 'method'})[['method', 'entry_date', 'entry_price', 'pnl']]
    a.to_csv(pub, mode='a', header=not os.path.exists(pub), index=False); b.to_csv(loc, mode='a', header=not os.path.exists(loc), index=False)


def round5():
    """R5, first-passage campaign (designed after R1-R4 were validated, selected on 2021-2023 only).
    Idea from first-passage-time theory: a profit target that is small next to the stock's monthly swing is
    reached in most trades, so most months end with every trade a winner; what is given up is that the trades
    which miss the target lose more. Entries come from the R1 model, with a lower bar so that there is a trade
    in most months."""
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    panel, D, cal, feats, cnq, path, bench, T = setup()
    train_days = cal[cal <= L.TRAIN_END]; VAL_END = str(train_days[-21].date())
    grid = [dict(src=src, H=5, side='long', q=q, hold=hold, target=t, stop=st)
            for src, q in (('always', None), ('gbm', 0.5), ('gbm', 0.7)) for t in (2.0, 3.0, 4.0) for hold in (10, 20) for st in (None, 10.0)]
    res = {}
    for cfg in grid:
        sig = signal_from_cfg(cfg, cnq, frozen['oof']).reindex(train_days).fillna(0)
        _, st = evaluate(path, bench, sig, cfg['hold'], cfg['target'], cfg['stop'], VAL_YEARS, end=VAL_END)
        res[json.dumps(cfg, sort_keys=True)] = st
    def level1(v):
        return all(p['n'] and p['G'] >= 1 and p['WR'] >= 50 and p['S'] >= 8 for p in v['per_year'].values())
    passers = {k: v for k, v in res.items() if level1(v)}
    if passers:
        best = max(passers, key=lambda k: passers[k]['worst_year_excess'])
    else:
        best = max(res, key=lambda k: (min(res[k]['S']), res[k]['G']))
    wf = json.load(open(f'{RES}/stage13_walkforward_results.json'))
    wf['rounds']['R5_first_passage'] = dict(settings=res, chosen=json.loads(best), level1_in_every_validation_year=sorted(passers),
                                            chosen_stats=res[best], strict_view=strict_view(res, VAL_YEARS),
                                            rule='settings that reach G1, WR1 and S1 in each of 2021, 2022, 2023; among them the best worst-year '
                                                 'excess over entering every day with the same exit; if none, the highest worst-year S, then G')
    json.dump(wf, open(f'{RES}/stage13_walkforward_results.json', 'w'), indent=1, default=str)
    fz = dict(chosen={'R5_first_passage': json.loads(best)}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'], gbm_params=GBM)
    pickle.dump(fz, open(f'{RES}/stage13_frozen_R5.pkl', 'wb'))
    rows = sorted(res.items(), key=lambda kv: -(min(kv[1]['S']) * 100 + (kv[1]['worst_year_excess'] or -9)))
    for k, v in rows[:12]:
        c = json.loads(k)
        print(c['src'], c['q'], 'T', c['target'], 'hold', c['hold'], 'stop', c['stop'], '| n', v['n'], 'G', v['G'], 'WR', v['WR'], 'S', v['S'],
              'ex', v['excess'], 'worst-yr ex', v['worst_year_excess'], 'L1' if level1(v) else '')
    print('passers', len(passers), 'chosen', best, flush=True)


def round6():
    """R6, one-a-month campaign (designed after R5's blind result; selected on 2021-2023 only).
    One trade per calendar month, on the first day the R1 model's score clears a bar; exit at a profit target
    or after a long time limit; trades may overlap. With one trade a month, a month counts toward S when that
    trade makes more than 1%, so the target is set above 1% and the time limit is long."""
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    panel, D, cal, feats, cnq, path, bench, T = setup()
    train_days = cal[cal <= L.TRAIN_END]
    grid = [dict(src='gbm', H=5, side='long', q=q, monthly=True, overlap=True, hold=hold, target=t, stop=None)
            for q in (0.5, 0.7) for t in (3.0, 4.0, 5.0) for hold in (20, 40, 60)]
    res = {}
    for cfg in grid:
        end = train_days[-cfg['hold'] - 1]                                  # every exit falls inside 2023
        sig = signal_from_cfg(cfg, cnq, frozen['oof']).reindex(train_days).fillna(0)
        _, st = evaluate(path, bench, sig, cfg['hold'], cfg['target'], cfg['stop'], VAL_YEARS, end=str(end.date()), overlap=True)
        st['months_available'] = {y: (12 if y < 2023 else int(end.month)) for y in VAL_YEARS}
        res[json.dumps(cfg, sort_keys=True)] = st
    def level1(v):
        return all(p['n'] and p['G'] >= 1 and p['WR'] >= 50 and p['S'] >= int(np.ceil(8 / 12 * v['months_available'][int(y)]))
                   for y, p in v['per_year'].items())
    passers = {k: v for k, v in res.items() if level1(v)}
    best = max(passers, key=lambda k: passers[k]['worst_year_excess']) if passers else max(res, key=lambda k: (min(res[k]['S']), res[k]['G']))
    wf = json.load(open(f'{RES}/stage13_walkforward_results.json'))
    wf['rounds']['R6_one_a_month'] = dict(settings=res, chosen=json.loads(best), level1_in_every_validation_year=sorted(passers), chosen_stats=res[best],
                                          rule='as R5; S judged on 8/12 of the months available in each validation year')
    json.dump(wf, open(f'{RES}/stage13_walkforward_results.json', 'w'), indent=1, default=str)
    pickle.dump(dict(chosen={'R6_one_a_month': json.loads(best)}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'], gbm_params=GBM),
                open(f'{RES}/stage13_frozen_R6.pkl', 'wb'))
    for k, v in sorted(res.items(), key=lambda kv: -(kv[1]['worst_year_excess'] or -9)):
        c = json.loads(k)
        print('q', c['q'], 'T', c['target'], 'hold', c['hold'], '| n', v['n'], 'G', v['G'], 'WR', v['WR'], 'S', v['S'], 'ex', v['excess'],
              'worst-yr ex', v['worst_year_excess'], [(p['G']) for p in v['per_year'].values()], 'L1' if level1(v) else '')
    print('passers', len(passers), 'chosen', best, flush=True)


def round7():
    """R7, one-a-month campaign inside the owner's risk rule (added 2026-11-23): no trade may lose more than 5%,
    so every trade carries a 5% stop. Same entry idea as R6; target, time limit and entry bar re-selected on
    2021-2023 only."""
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    panel, D, cal, feats, cnq, path, bench, T = setup()
    train_days = cal[cal <= L.TRAIN_END]
    grid = [dict(src='gbm', H=5, side='long', q=q, monthly=True, overlap=True, hold=hold, target=t, stop=5.0)
            for q in (0.5, 0.7, 0.85) for t in (2.0, 3.0, 4.0, 5.0) for hold in (20, 40, 60)]
    res = {}
    for cfg in grid:
        end = train_days[-cfg['hold'] - 1]
        sig = signal_from_cfg(cfg, cnq, frozen['oof']).reindex(train_days).fillna(0)
        _, st = evaluate(path, bench, sig, cfg['hold'], cfg['target'], cfg['stop'], VAL_YEARS, end=str(end.date()), overlap=True)
        st['months_available'] = {y: (12 if y < 2023 else int(end.month)) for y in VAL_YEARS}
        res[json.dumps(cfg, sort_keys=True)] = st
    def level1(v):
        return all(p['n'] and p['G'] >= 1 and p['WR'] >= 50 and p['S'] >= int(np.ceil(8 / 12 * v['months_available'][int(y)]))
                   for y, p in v['per_year'].items())
    passers = {k: v for k, v in res.items() if level1(v)}
    best = max(passers, key=lambda k: passers[k]['worst_year_excess']) if passers else max(res, key=lambda k: (min(res[k]['S']), res[k]['G']))
    wf = json.load(open(f'{RES}/stage13_walkforward_results.json'))
    wf['rounds']['R7_one_a_month_stop5'] = dict(settings=res, chosen=json.loads(best), level1_in_every_validation_year=sorted(passers),
                                                chosen_stats=res[best], rule='as R6, every setting with a 5% stop')
    json.dump(wf, open(f'{RES}/stage13_walkforward_results.json', 'w'), indent=1, default=str)
    pickle.dump(dict(chosen={'R7_one_a_month_stop5': json.loads(best)}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'], gbm_params=GBM),
                open(f'{RES}/stage13_frozen_R7.pkl', 'wb'))
    for k, v in sorted(res.items(), key=lambda kv: -(min(kv[1]['S']) * 100 + (kv[1]['G'] or -9)))[:10]:
        c = json.loads(k)
        print('q', c['q'], 'T', c['target'], 'hold', c['hold'], '| n', v['n'], 'G', v['G'], 'WR', v['WR'], 'S', v['S'], 'ex', v['excess'],
              'worst-yr ex', v['worst_year_excess'], [(p['G']) for p in v['per_year'].values()], 'L1' if level1(v) else '')
    print('passers', len(passers), 'chosen', best, res[best]['S'], res[best]['G'], flush=True)


def round8():
    """R8: model E unchanged (top 15% of its own forecasts, 5 days) with the owner's 5% stop added. One setting,
    nothing selected. Also records, on 2021-2023 only, what model J's design does under stops of 5, 8, 10, 15%
    and none, so the owner can see the price of the limit without another look at 2024-2026."""
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    panel, D, cal, feats, cnq, path, bench, T = setup()
    train_days = cal[cal <= L.TRAIN_END]
    cfg = dict(src='gbm', H=5, side='long', q=0.85, target=None, stop=5.0)
    sig = signal_from_cfg(cfg, cnq, frozen['oof']).reindex(train_days).fillna(0)
    _, st = evaluate(path, bench, sig, 5, None, 5.0, VAL_YEARS, end=str(train_days[-11].date()))
    front = {}
    for stop in (5.0, 8.0, 10.0, 15.0, None):
        c = dict(src='gbm', H=5, side='long', q=0.5, monthly=True, overlap=True, hold=60, target=4.0, stop=stop)
        sg = signal_from_cfg(c, cnq, frozen['oof']).reindex(train_days).fillna(0)
        t, v = evaluate(path, bench, sg, 60, 4.0, stop, VAL_YEARS, end=str(train_days[-61].date()), overlap=True)
        front[str(stop)] = dict(n=v['n'], G=v['G'], WR=v['WR'], S=v['S'], excess=v['excess'], worst_trade=round(float(t.ret.min()), 2))
        print('J design, stop', stop, front[str(stop)], flush=True)
    wf = json.load(open(f'{RES}/stage13_walkforward_results.json'))
    wf['rounds']['R8_peer_fusion_stop5'] = dict(chosen=cfg, chosen_stats=st, rule='single setting: R1 with a 5% stop; nothing selected')
    wf['stop_frontier_J_design_validation_only'] = front
    json.dump(wf, open(f'{RES}/stage13_walkforward_results.json', 'w'), indent=1, default=str)
    pickle.dump(dict(chosen={'R8_peer_fusion_stop5': cfg}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'], gbm_params=GBM),
                open(f'{RES}/stage13_frozen_R8.pkl', 'wb'))
    print('R8 validation', {k: st[k] for k in ('n', 'G', 'WR', 'S', 'excess', 'worst_year_excess')}, flush=True)


def round9():
    """R9: model J unchanged (one trade a month, +4% target, 60 days) with a 15% stop, the owner's wider risk
    level. One setting, nothing selected; the stop level was priced on 2021-2023 in round8."""
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    panel, D, cal, feats, cnq, path, bench, T = setup()
    train_days = cal[cal <= L.TRAIN_END]
    cfg = dict(src='gbm', H=5, side='long', q=0.5, monthly=True, overlap=True, hold=60, target=4.0, stop=15.0)
    sig = signal_from_cfg(cfg, cnq, frozen['oof']).reindex(train_days).fillna(0)
    _, st = evaluate(path, bench, sig, 60, 4.0, 15.0, VAL_YEARS, end=str(train_days[-61].date()), overlap=True)
    wf = json.load(open(f'{RES}/stage13_walkforward_results.json'))
    wf['rounds']['R9_one_a_month_stop15'] = dict(chosen=cfg, chosen_stats=st, rule='single setting: R6 with a 15% stop; nothing selected')
    json.dump(wf, open(f'{RES}/stage13_walkforward_results.json', 'w'), indent=1, default=str)
    pickle.dump(dict(chosen={'R9_one_a_month_stop15': cfg}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'], gbm_params=GBM),
                open(f'{RES}/stage13_frozen_R9.pkl', 'wb'))
    print('R9 validation', {k: st[k] for k in ('n', 'G', 'WR', 'S', 'excess')}, [p['G'] for p in st['per_year'].values()], flush=True)


def round10():
    """R10: a monthly campaign aimed at level 1 on all FOUR goals (G, WR, S and GM, the month total of 5% or
    more), inside the 15% loss limit. One or two trades a month from the R1 model, a target large enough that
    the month's total can reach 5%, a 10% or 15% stop. Selected on 2021-2023 only; run it with
    S13_CUTOFF=2023-12-29 so the test years are not in the data at all."""
    assert os.environ.get('S13_CUTOFF', '') <= '2023-12-31' and os.environ.get('S13_CUTOFF'), 'run the selection with S13_CUTOFF=2023-12-29'
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    panel, D, cal, feats, cnq, path, bench, T = setup()
    assert cal.max() <= pd.Timestamp('2023-12-31')
    grid = [dict(src='gbm', H=5, side='long', q=0.5, monthly=True, per_month=k, overlap=True, hold=hold, target=t, stop=st)
            for k in (1, 2) for t in (4.0, 5.5, 6.0, 8.0) for st in (10.0, 15.0) for hold in (40, 60)]
    res = {}
    for cfg in grid:
        end = cal[-cfg['hold'] - 1]
        sig = signal_from_cfg(cfg, cnq, frozen['oof']).reindex(cal).fillna(0)
        t = L.run_trades(path, sig, cfg['hold'], cfg['target'], cfg['stop'], start='2021-01-01', end=str(end.date()), overlap=True)
        per = {}
        for y in VAL_YEARS:
            ty = t[t.entry_date.dt.year == y]; avail = 12 if y < 2023 else int(end.month); g = ty.groupby(ty.entry_date.dt.month).ret
            per[y] = dict(n=int(len(ty)), G=round(float(ty.ret.mean()), 3) if len(ty) else -9.0, WR=round(float((ty.ret > 0).mean() * 100), 1) if len(ty) else 0.0,
                          S=int((g.mean() > 1).sum()), GM=int((g.sum() >= 5).sum()), months=avail)
        need = lambda p: int(np.ceil(8 / 12 * p['months']))
        ok = all(p['G'] >= 1 and p['WR'] >= 50 and p['S'] >= need(p) and p['GM'] >= need(p) for p in per.values())
        res[json.dumps(cfg, sort_keys=True)] = dict(n=int(len(t)), G=round(float(t.ret.mean()), 3), WR=round(float((t.ret > 0).mean() * 100), 1),
                                                    worst=round(float(t.ret.min()), 1), per_year=per, level1_all_four_every_year=bool(ok),
                                                    margin=min(min(p['S'], p['GM']) / p['months'] for p in per.values()))
    passers = {k: v for k, v in res.items() if v['level1_all_four_every_year']}
    for k, v in sorted(res.items(), key=lambda kv: -(kv[1]['margin'] * 100 + kv[1]['G']))[:8]:
        c = json.loads(k)
        print('per month', c['per_month'], 'T', c['target'], 'stop', c['stop'], 'hold', c['hold'], '| n', v['n'], 'G', v['G'], 'WR', v['WR'],
              'S', [p['S'] for p in v['per_year'].values()], 'GM', [p['GM'] for p in v['per_year'].values()], 'G by yr', [p['G'] for p in v['per_year'].values()],
              'L1x4' if v['level1_all_four_every_year'] else '', flush=True)
    wf = json.load(open(f'{RES}/stage13_walkforward_results.json'))
    entry = dict(settings=res, level1_all_four_in_every_validation_year=sorted(passers),
                 rule='settings that reach G1, WR1, S1 and GM1 in each of 2021, 2022, 2023; among them the widest margin on the two month goals, then G; '
                      'if none passes, no model is frozen and nothing is run on 2024-2026')
    if passers:
        best = max(passers, key=lambda k: (passers[k]['margin'], passers[k]['G']))
        entry.update(chosen=json.loads(best), chosen_stats=res[best])
        pickle.dump(dict(chosen={'R10_monthly_campaign_four_goals': json.loads(best)}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'], gbm_params=GBM),
                    open(f'{RES}/stage13_frozen_R10.pkl', 'wb'))
        print('chosen', best, flush=True)
    wf['rounds']['R10_monthly_campaign_four_goals'] = entry
    json.dump(wf, open(f'{RES}/stage13_walkforward_results.json', 'w'), indent=1, default=str)
    print('passers', len(passers), 'of', len(res), flush=True)


if __name__ == '__main__':
    os.makedirs(RES, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'walkforward':
        walkforward()
    elif mode == 'round10':
        round10()
    elif mode == 'round9':
        round9()
    elif mode == 'round8':
        round8()
    elif mode == 'round7':
        round7()
    elif mode == 'round6':
        round6()
    elif mode == 'round5':
        round5()
    elif mode == 'blind':
        blind(sys.argv[2] if len(sys.argv) > 2 else 'stage13_frozen.pkl')
    elif mode == 'verify':
        blind(sys.argv[2] if len(sys.argv) > 2 else 'stage13_frozen.pkl', verify=True)
    else:
        print(__doc__)
