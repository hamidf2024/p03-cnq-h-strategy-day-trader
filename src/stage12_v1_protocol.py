"""
SUPERSEDED FIRST PROTOCOL (v1), kept for the record -- see stage12_field_fusion.py for the
protocol that was frozen and blind-tested. v1 was run on 2020-2023 only and never touched
2024-2026. It was replaced because (1) its inner-split thresholds were unstable from fold to
fold and (2) entering on the first stretched day bought into falls that were still in
progress (2022). The blind mode below was never executed.

Stage 12 -- "Field-Fusion Swing" research cycle for CNQ.

Target (owner, 2026-11-23): more than 1% average GROSS return per trade over
2024-2026, trained walk-forward on 2020-2023 and tested blind on 2024-2026.

Three pre-declared candidate families, all multi-day (swing) long-only,
one position at a time, entry and exit at the daily close, decision taken
one 5-minute bar before the close (see s12_lib.py for the timing rules):

  A  "Spring"       physics rule only. Kalman-filter equilibrium (control
                    engineering); enter when the displacement z-score is
                    stretched below -k (a loaded spring / Ornstein-Uhlenbeck
                    excursion); exit after H days.
                    Grid: span {10,20} x k {1.0,1.5,2.0} x H {5,10} = 12.
  B  "Field-Fusion" gradient-boosted model over 33 causal features drawn
                    from control engineering, stochastic calculus, statistical
                    physics / information theory, rough-path signatures,
                    realised-volatility econometrics and overnight/intraday
                    microstructure. Predicts the H-day return in excess of the
                    training mean for EVERY day (so it learns from ~800 labels,
                    not ~40 events); trades when the prediction is in the top
                    (1-q) of predictions. Grid: H {5,10} x q {0.8,0.9} = 4.
  C  "Transformer"  PatchTST-style encoder, self-supervised pretraining on
                    5-minute bars, frozen, ridge probe. Same trading rule and
                    grid as B.

Walk-forward folds (inside 2020-2023 only):
  fold1 train 2020 -> validate 2021; fold2 train 2020-21 -> validate 2022;
  fold3 train 2020-22 -> validate 2023. Labels that overlap the validation
  year are purged from training. Probability/return thresholds are chosen on
  an inner time split of each fold's own training window.

Selection (declared before any validation number was looked at):
  score = t-statistic of the per-trade EXCESS return (trade return minus the
  average same-length return of all days in that year), pooled over the three
  validation years; a config needs >= 30 pooled validation trades. Excess is
  used so that 2020-2023's strong upward drift cannot pick the winner.
  The family/config with the best score is the official Stage 12 model. All
  three families are frozen and ALL are reported on the blind years.

Modes:
  python3 src/stage12_field_fusion.py walkforward   (reads rows < 2024-01-01 only)
  python3 src/stage12_field_fusion.py blind         (2024-2026, frozen artefacts, run once)
"""
import sys, os, json, pickle, itertools, hashlib, time, warnings
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from s12_lib import (load_5min, build_daily, add_features, simulate, stats, FEATURES)

TRAIN_END = '2024-01-01'
FOLDS = [((2020,), 2021), ((2020, 2021), 2022), ((2020, 2021, 2022), 2023)]
A_GRID = list(itertools.product((10, 20), (1.0, 1.5, 2.0), (5, 10)))
ML_GRID = list(itertools.product((5, 10), (0.8, 0.9)))
SPAN_ML = 20
MIN_POOLED = 30
A_FLOOR = 8
SEEDS = (0, 1, 2, 3, 4)
RES = 'results/experiments'


# ----------------------------------------------------------------- helpers
def fwd(d, H):
    return (d.c.shift(-H) / d.c - 1) * 100


def year_drift(d, H):
    f = fwd(d, H)
    return f.groupby(d.index.year).mean().to_dict()


def add_excess(tr, drift):
    tr = tr.copy()
    if len(tr):
        tr['yr'] = tr.entry_date.dt.year
        tr['excess'] = tr.ret - tr.yr.map(drift)
    else:
        tr['yr'] = []; tr['excess'] = []
    return tr


def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return float('nan')
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def summ(tr):
    s = stats(tr)
    if len(tr):
        s['excess'] = float(tr.excess.mean()); s['t_excess'] = tstat(tr.excess)
        s['t_raw'] = tstat(tr.ret)
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in s.items()}


def train_rows(d, ok, years, H, last_allowed_pos):
    """Row positions usable for training: in `years`, features complete,
    label complete, and label window ending on or before last_allowed_pos."""
    pos = np.where(ok & np.isin(d.index.year, years))[0]
    return pos[pos + H <= last_allowed_pos]


def fit_gbm(X, y):
    models = []
    for s in SEEDS:
        m = GradientBoostingRegressor(loss='huber', n_estimators=60, max_depth=2, learning_rate=0.05,
                                      subsample=0.8, min_samples_leaf=10, random_state=s)
        models.append(m.fit(X, y))
    return models


def pred_gbm(models, X):
    return np.mean([m.predict(X) for m in models], axis=0)


def fit_ridge(X, y):
    sc = StandardScaler().fit(X)
    m = RidgeCV(alphas=[10.0, 100.0, 1000.0, 10000.0]).fit(np.clip(sc.transform(X), -4, 4), y)
    return (sc, m)


def pred_ridge(sm, X):
    sc, m = sm
    return m.predict(np.clip(sc.transform(X), -4, 4))


def fit_with_threshold(X, y, q, fit, pred):
    """Threshold = q-quantile of out-of-sample predictions on the last 28% of
    the training window (model fitted on the first 72%); then refit on all."""
    n = len(X); cut = int(n * 0.72)
    inner = fit(X[:cut], y[:cut] - y[:cut].mean())
    tau = float(np.quantile(pred(inner, X[cut:]), q))
    mu = float(y.mean())
    model = fit(X, y - mu)
    return model, tau, mu


# --------------------------------------------------------- transformer glue
def transformer_embeddings(df5, d, fit_years, seed=0, verbose=False):
    from s12_transformer import day_tensor, window, pretrain, embed_all
    dates = list(d.index)
    arrs = day_tensor(df5, d.vol20.to_dict())
    wins = {i: window(arrs, dates, i) for i in range(len(dates))}
    fit_idx = [i for i in range(len(dates)) if wins[i] is not None and dates[i].year in fit_years]
    model, hist = pretrain([wins[i] for i in fit_idx], seed=seed, verbose=verbose)
    valid = [i for i in range(len(dates)) if wins[i] is not None]
    E = np.full((len(dates), 96), np.nan, dtype=np.float32)
    E[valid] = embed_all(model, [wins[i] for i in valid])
    return E, model, hist


# ------------------------------------------------------------- walk-forward
def walkforward():
    t0 = time.time()
    df5 = load_5min(end=TRAIN_END)
    assert df5.Datetime.max() < pd.Timestamp(TRAIN_END)
    base = build_daily(df5)
    print(f'[walkforward] training rows only: {len(df5):,} bars, {len(base)} days, '
          f'{base.index[0].date()} .. {base.index[-1].date()}')
    n = len(base)
    out = {'meta': {'train_end': TRAIN_END, 'days': n, 'folds': [list(map(str, f)) for f in FOLDS]}}

    # ---------------- family A ------------------------------------------
    A = {}
    feats_span = {s: add_features(base, s) for s in (10, 20)}
    trades_A = {}
    for span, k, H in A_GRID:
        d = feats_span[span]
        tr = simulate(d, (d.z <= -k).values, H=H)
        trades_A[(span, k, H)] = add_excess(tr, year_drift(d, H))

    def pick_A(years):
        best, bs = None, -np.inf
        for cfg, tr in trades_A.items():
            t = tr[tr.yr.isin(years)]
            if len(t) < A_FLOOR:
                continue
            s = tstat(t.excess)
            if np.isfinite(s) and s > bs:
                best, bs = cfg, s
        return best, bs

    A['folds'] = []
    valA = []
    for years, vy in FOLDS:
        cfg, s = pick_A(years)
        rec = {'train_years': years, 'val_year': vy, 'chosen': cfg, 'train_score': None if cfg is None else round(s, 3)}
        if cfg is not None:
            tr = trades_A[cfg]
            rec['train'] = summ(tr[tr.yr.isin(years)])
            v = tr[tr.yr == vy]
            rec['val'] = summ(v)
            valA.append(v)
        else:
            rec['note'] = f'no candidate cleared the {A_FLOOR}-trade floor on the training years'
        A['folds'].append(rec)
        print('  A fold', years, '->', vy, rec.get('chosen'), rec.get('val'))
    poolA = pd.concat(valA) if valA else pd.DataFrame(columns=['ret', 'excess', 'days', 'entry'])
    A['pooled_val'] = summ(poolA)
    cfgA, sA = pick_A((2020, 2021, 2022, 2023))
    A['final'] = {'chosen': cfgA, 'train_score': round(sA, 3), 'train': summ(trades_A[cfgA])}
    A['grid_train_2020_2023'] = {str(c): summ(t) for c, t in trades_A.items()}
    print('  A pooled validation:', A['pooled_val'], '| final config', cfgA)
    out['A'] = A

    # ---------------- family B and C ------------------------------------
    d = feats_span[SPAN_ML]
    ok = d[FEATURES].notna().all(1).values
    X = d[FEATURES].values
    yrs = d.index.year.values

    def run_family(name, feat_fn):
        """feat_fn(fold_years) -> (matrix, ok_mask, fit, pred)"""
        fam = {'configs': {}}
        cache = {}
        pooled = {}
        for H, q in ML_GRID:
            drift = year_drift(d, H)
            y = fwd(d, H).values
            vals = []; frec = []
            for years, vy in FOLDS:
                key = tuple(years)
                if key not in cache:
                    cache[key] = feat_fn(years)
                M, okm, fit, pred = cache[key]
                last_tr = np.where(np.isin(yrs, years))[0].max()
                tr_pos = train_rows(d, okm, years, H, last_tr)
                if len(tr_pos) < 40:
                    frec.append({'val_year': vy, 'note': f'only {len(tr_pos)} training rows -- fold skipped'})
                    continue
                model, tau, mu = fit_with_threshold(M[tr_pos], y[tr_pos], q, fit, pred)
                te = okm & (yrs == vy)
                p = np.full(n, -np.inf); p[te] = pred(model, M[te])
                tr = add_excess(simulate(d, p >= tau, H=H), drift)
                ic = float(pd.Series(p[te]).corr(pd.Series(y[te]), method='spearman'))
                frec.append({'val_year': vy, 'n_train': int(len(tr_pos)), 'tau': round(tau, 4),
                             'val_rank_ic': round(ic, 4), 'val': summ(tr)})
                vals.append(tr)
            pool = pd.concat(vals) if vals else pd.DataFrame(columns=['ret', 'excess', 'days', 'entry'])
            pooled[(H, q)] = pool
            fam['configs'][f'H={H},q={q}'] = {'folds': frec, 'pooled_val': summ(pool)}
            print(f'  {name} H={H} q={q} pooled validation:', summ(pool))
        # choose config
        best, bs = None, -np.inf
        for cfg, pool in pooled.items():
            if len(pool) < MIN_POOLED:
                continue
            s = tstat(pool.excess)
            if np.isfinite(s) and s > bs:
                best, bs = cfg, s
        fam['chosen'] = None if best is None else {'H': best[0], 'q': best[1], 'score_t_excess': round(bs, 3)}
        fam['pooled_val_chosen'] = summ(pooled[best]) if best else None
        return fam, best, (pooled[best] if best else None)

    def feat_B(years):
        return X, ok, fit_gbm, pred_gbm
    B, cfgB, poolB = run_family('B', feat_B)
    out['B'] = B

    emb_cache = {}

    def feat_C(years):
        E, model, hist = transformer_embeddings(df5, d, set(years), seed=0)
        emb_cache[tuple(years)] = hist
        okE = np.isfinite(E).all(1) & np.isfinite(d.vol20.values)
        return np.nan_to_num(E), okE, fit_ridge, pred_ridge
    print('  C: pretraining transformer per fold (CPU) ...')
    C, cfgC, poolC = run_family('C', feat_C)
    C['pretrain_loss_first_last'] = {str(k): [round(v[0], 4), round(v[-1], 4)] for k, v in emb_cache.items()}
    out['C'] = C

    # ---------------- family selection ----------------------------------
    scores = {'A': tstat(poolA.excess) if len(poolA) >= MIN_POOLED else float('nan'),
              'B': B['chosen']['score_t_excess'] if B['chosen'] else float('nan'),
              'C': C['chosen']['score_t_excess'] if C['chosen'] else float('nan')}
    official = max((k for k in scores if np.isfinite(scores[k])), key=lambda k: scores[k], default=None)
    out['selection'] = {'scores_t_excess_pooled_validation': {k: (None if not np.isfinite(v) else round(v, 3)) for k, v in scores.items()},
                        'official': official,
                        'rule': f'highest pooled-validation t-stat of excess return, >= {MIN_POOLED} pooled validation trades'}
    print('  selection scores:', out['selection'])

    # ---------------- final fits on all of 2020-2023 --------------------
    frozen = {'A': {'span': cfgA[0], 'k': cfgA[1], 'H': cfgA[2]}, 'official': official,
              'features': FEATURES, 'span_ml': SPAN_ML}
    all_years = (2020, 2021, 2022, 2023)
    last_tr = n - 1
    if cfgB:
        H, q = cfgB
        y = fwd(d, H).values
        pos = train_rows(d, ok, all_years, H, last_tr)
        model, tau, mu = fit_with_threshold(X[pos], y[pos], q, fit_gbm, pred_gbm)
        frozen['B'] = {'H': H, 'q': q, 'tau': tau, 'train_mean': mu, 'n_train': int(len(pos)), 'models': model}
        imp = np.mean([m.feature_importances_ for m in model], axis=0)
        out['B']['final_feature_importance'] = {f: round(float(v), 4) for f, v in sorted(zip(FEATURES, imp), key=lambda t: -t[1])}
        out['B']['final'] = {'H': H, 'q': q, 'tau': round(tau, 4), 'train_mean_fwd': round(mu, 4), 'n_train': int(len(pos))}
    if cfgC:
        H, q = cfgC
        y = fwd(d, H).values
        E, tmodel, hist = transformer_embeddings(df5, d, set(all_years), seed=0)
        okE = np.isfinite(E).all(1) & np.isfinite(d.vol20.values)
        pos = train_rows(d, okE, all_years, H, last_tr)
        model, tau, mu = fit_with_threshold(np.nan_to_num(E)[pos], y[pos], q, fit_ridge, pred_ridge)
        import torch
        frozen['C'] = {'H': H, 'q': q, 'tau': tau, 'train_mean': mu, 'n_train': int(len(pos)),
                       'probe': model, 'state_dict': {k: v.numpy() for k, v in tmodel.state_dict().items()}}
        out['C']['final'] = {'H': H, 'q': q, 'tau': round(tau, 4), 'n_train': int(len(pos))}
    # regression fingerprint: features on training days, to be re-checked in the blind run
    frozen['feature_fingerprint'] = hashlib.sha256(np.round(np.nan_to_num(X), 8).tobytes()).hexdigest()
    frozen['n_train_days'] = n
    os.makedirs(RES, exist_ok=True)
    with open(f'{RES}/stage12_frozen_v1_not_used.pkl', 'wb') as f:
        pickle.dump(frozen, f)
    out['meta']['frozen_sha256'] = hashlib.sha256(open(f'{RES}/stage12_frozen_v1_not_used.pkl', 'rb').read()).hexdigest()
    out['meta']['runtime_s'] = round(time.time() - t0, 1)
    json.dump(out, open(f'{RES}/stage12_walkforward_v1_results.json', 'w'), indent=1, default=str)
    print(f'[walkforward] done in {time.time() - t0:.0f}s; frozen artefact sha256 {out["meta"]["frozen_sha256"][:16]}...')


# ------------------------------------------------------------------- blind
def boot_ci(x, n=10000, seed=0):
    x = np.asarray(x, float)
    if len(x) < 3:
        return [float('nan'), float('nan')]
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (n, len(x)), replace=True).mean(1)
    return [round(float(np.quantile(m, 0.025)), 3), round(float(np.quantile(m, 0.975)), 3)]


def blind(verify=False):
    marker = f'{RES}/stage12_BLIND_RUN_LOG.json'
    frozen_bytes = open(f'{RES}/stage12_frozen_v1_not_used.pkl', 'rb').read()
    fsha = hashlib.sha256(frozen_bytes).hexdigest()
    log = json.load(open(marker)) if os.path.exists(marker) else []
    if log and not verify:
        sys.exit('Blind test has already been run once. Use "verify" to re-run the SAME frozen artefact for reproducibility only.')
    if verify and log and log[0]['frozen_sha256'] != fsha:
        sys.exit('Frozen artefact changed since the blind run -- refusing.')
    frozen = pickle.loads(frozen_bytes)
    df5 = load_5min()
    base = build_daily(df5)
    d = add_features(base, frozen['span_ml'])
    n_tr = frozen['n_train_days']
    Xall = d[FEATURES].values
    fp = hashlib.sha256(np.round(np.nan_to_num(Xall[:n_tr]), 8).tobytes()).hexdigest()
    assert fp == frozen['feature_fingerprint'], 'training-period features differ between cut and full builds (look-ahead?)'
    print('[blind] regression check passed: features for 2020-2023 are identical with and without 2024+ data present')
    yrs = d.index.year.values
    blind_mask = yrs >= 2024
    res = {'meta': {'frozen_sha256': fsha, 'official': frozen['official'], 'blind_days': int(blind_mask.sum()),
                    'first': str(d.index[blind_mask][0].date()), 'last': str(d.index[-1].date())}}
    trades_out = []

    def report(name, tr, H, dd):
        drift = year_drift(dd[blind_mask], H)
        tr = add_excess(tr, drift)
        r = {'config_H': H, 'by_year': {}, 'drift_avg_Hday_ret_by_year': {int(k): round(v, 3) for k, v in drift.items()}}
        for y in (2024, 2025, 2026):
            r['by_year'][y] = summ(tr[tr.yr == y])
        c = summ(tr)
        c['avg_ci95_bootstrap'] = boot_ci(tr.ret.values)
        c['excess_ci95_bootstrap'] = boot_ci(tr.excess.values)
        c['avg_net_at_1c_per_share'] = round(float((tr.ret - 100 * 0.01 / tr.entry).mean()), 4) if len(tr) else None
        c['avg_net_at_10bps_round_trip'] = round(float(tr.ret.mean() - 0.10), 4) if len(tr) else None
        c['share_of_trades_above_1pct'] = round(float((tr.ret > 1).mean() * 100), 1) if len(tr) else None
        c['max_consecutive_losses'] = int(max((sum(1 for _ in g) for k, g in itertools.groupby(tr.ret < 0) if k), default=0))
        c['equity_max_drawdown_pct_sum'] = round(float((tr.ret.cumsum() - tr.ret.cumsum().cummax()).min()), 2) if len(tr) else None
        r['combined_2024_2026'] = c
        res[name] = r
        t = tr.copy(); t.insert(0, 'model', name); trades_out.append(t)
        print(f'  {name}: combined {c}')
        for y in (2024, 2025, 2026):
            print(f'     {y}: {r["by_year"][y]}')

    # A
    a = frozen['A']
    dA = add_features(base, a['span'])
    sig = (dA.z <= -a['k']).values & blind_mask
    report('A_spring', simulate(dA, sig, H=a['H']), a['H'], dA)
    # B
    if 'B' in frozen:
        b = frozen['B']
        okb = d[FEATURES].notna().all(1).values & blind_mask
        p = np.full(len(d), -np.inf); p[okb] = pred_gbm(b['models'], Xall[okb])
        report('B_field_fusion_gbm', simulate(d, p >= b['tau'], H=b['H']), b['H'], d)
        res['B_field_fusion_gbm']['signal_days'] = int((p >= b['tau']).sum())
        yb = fwd(d, b['H']).values
        m = okb & np.isfinite(yb)
        res['B_field_fusion_gbm']['blind_rank_ic'] = round(float(pd.Series(p[m]).corr(pd.Series(yb[m]), method='spearman')), 4)
    # C
    if 'C' in frozen:
        import torch
        from s12_transformer import day_tensor, window, embed_all, PatchEncoder
        c = frozen['C']
        tm = PatchEncoder(); tm.load_state_dict({k: torch.tensor(v) for k, v in c['state_dict'].items()}); tm.eval()
        dates = list(d.index)
        arrs = day_tensor(df5, d.vol20.to_dict())
        wins = {i: window(arrs, dates, i) for i in range(len(dates))}
        valid = [i for i in range(len(dates)) if wins[i] is not None and blind_mask[i]]
        E = embed_all(tm, [wins[i] for i in valid])
        p = np.full(len(d), -np.inf); p[valid] = pred_ridge(c['probe'], E)
        report('C_transformer_probe', simulate(d, p >= c['tau'], H=c['H']), c['H'], d)
        yc = fwd(d, c['H']).values
        m = np.isfinite(p) & np.isfinite(yc) & blind_mask
        res['C_transformer_probe']['blind_rank_ic'] = round(float(pd.Series(p[m]).corr(pd.Series(yc[m]), method='spearman')), 4)
    # buy-and-hold context
    cb = d.c[blind_mask]
    res['context'] = {'buy_and_hold_2024_2026_pct': round(float((cb.iloc[-1] / cb.iloc[0] - 1) * 100), 2),
                      'avg_daily_ret_pct': round(float(cb.pct_change().mean() * 100), 4),
                      'avg_5day_ret_pct': round(float(fwd(d, 5)[blind_mask].mean()), 3),
                      'avg_10day_ret_pct': round(float(fwd(d, 10)[blind_mask].mean()), 3)}
    print('  context:', res['context'])
    if not verify:
        json.dump(res, open(f'{RES}/stage12_blind_results.json', 'w'), indent=1, default=str)
        pd.concat(trades_out).to_csv(f'{RES}/stage12_blind_trades.csv', index=False)
        log.append({'when_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'frozen_sha256': fsha})
        json.dump(log, open(marker, 'w'), indent=1)
        print('[blind] results written; blind run logged (one run only).')
    else:
        prev = json.load(open(f'{RES}/stage12_blind_results.json'))
        same = json.dumps(prev, sort_keys=True, default=str) == json.dumps(json.loads(json.dumps(res, default=str)), sort_keys=True)
        print('[verify] re-run reproduces the stored blind results exactly:', same)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'walkforward':
        walkforward()
    elif mode == 'blind':
        blind()
    elif mode == 'verify':
        blind(verify=True)
    else:
        print(__doc__)
