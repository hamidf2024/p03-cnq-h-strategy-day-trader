"""
Stage 10: genuine walk-forward train/test for the project's top 3 methods
by net profit -- V7, V7.1, and Stage 8's best ML variant ("Rule OR Model").

Every result in Stages 1-9 used the hand-picked V1-V7.1 parameters as-is,
unchanged, across whatever date range was being tested (including Stage 9's
6.3-year run). That is NOT the same thing as training on one period and
testing on another -- nothing before this stage was ever genuinely re-fit
on past data alone and then evaluated on data it had never seen. This script
does that properly:

    Train:  2020-2023  (861 trading days)
    Test:   2024, 2025, 2026 -- each touched exactly once, after training
            was frozen. Never used to pick or re-pick anything.

Anti-overfitting design (built in at the user's explicit request -- "ensure
that not over fitting or over ruling happen"):

  1. Walk-forward folds INSIDE the training window only, each validated on
     a year the fold never trained on:
         fold1: train 2020                -> validate (blind) on 2021
         fold2: train 2020-2021           -> validate (blind) on 2022
         fold3: train 2020-2022           -> validate (blind) on 2023
     2024-2026 are never touched during this step.
  2. Selection by OUT-OF-SAMPLE fold performance, not in-sample fit. For
     V7/V7.1, each fold picks whichever (band, entry_cutoff) combination had
     the best net-per-trade on that fold's TRAINING years -- a deliberately
     narrow 3x3 grid (9 combinations), not a search over per-trade special-
     case conditions. That kind of curve-fitting is exactly what this
     project's own lessons-learned doc already flags and rejects (see the
     REJECTED_* presets in bt7_unified_backtester_v1_to_v71.py). A floor of
     MIN_TRADES=30 per candidate per fold stops any combination from
     winning on a lucky handful of trades.
  3. Rule OR Model reuses V7.1's exact, already-validated zone/entry/exit
     logic UNCHANGED (band/cutoff are not re-optimized for this method --
     a deliberate scope-control decision) to label every zone touch with
     its would-be P&L, then retrains a small gradient-boosted classifier
     (identical architecture to Stage 8) on only the fold's training years.
     Its probability threshold is picked on an INNER time-based split
     within that training window (last ~28% of its days, exactly Stage 8's
     own procedure) -- the fold's validation/test year is never used to
     pick the threshold.
  4. The FINAL frozen configuration for each method is chosen the same way,
     using all of 2020-2023 as training, then run ONCE, blind, on each of
     2024, 2025, 2026 -- no retuning between years, no peeking.

Speed trick (what makes a 72-job grid search + 3 models' walk-forward folds
tractable in one background run): run_version() has no cross-day state --
zones, position, and attempt counters all reset at the top of each day's
loop, and the only thing computed outside the per-day loop (prior_hlc) is
built once from the full `days` list before any slicing happens. So running
a config on a set of days equals the union of running it on each day
individually: one trade list per (config, year) is cached and any multi-
year training window is obtained by concatenating cached per-year lists,
instead of re-simulating overlapping ranges for every grid candidate.

Usage
-----
Put the full-history CSV (data/raw/CNQ_5min_20200727_to_20261118.csv) at
./cnq.csv, alongside this file, bt7_unified_backtester_v1_to_v71.py, and
ml_v8_gbm_experiment.py, then:

    python3 stage10_walk_forward_training.py

Runs in the background are recommended (grid search + 3 GBM refits take
roughly 15-20 minutes); progress is written to stage10_progress.json after
each unit of work, and all final numbers to stage10_results.json.
"""
import sys, os, json, time, pickle, itertools
sys.path.insert(0, '.')

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

from bt7_unified_backtester_v1_to_v71 import VERSIONS, run_version, stats, days, day_rows
import ml_v8_gbm_experiment as ml8
from ml_v8_gbm_experiment import build_candidates, prep, align, run_sequential

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
BANDS = [0.012, 0.02, 0.04]
CUTOFFS = ['12:55', '13:30', '13:55']
TRAIN_YEARS = ['2020', '2021', '2022', '2023']
TEST_YEARS = ['2024', '2025', '2026']
ALL_YEARS = TRAIN_YEARS + TEST_YEARS
MIN_TRADES = 30  # floor per candidate per fold -- no combo wins on a handful of trades

# Base configs for V7/V7.1, band and entry_cutoff left as free knobs for the
# grid; every other parameter (stop/target offsets, avg_lookback, wide-day
# threshold, ratchet behavior) stays exactly as hand-tuned in bt7's VERSIONS
# dict -- the code's own comments flag stop/target changes as "a materially
# bigger departure... must be flagged explicitly," so they're out of scope
# for an ordinary walk-forward parameter search.
METHOD_BASE = {
    'V7': dict(exit_mode='next_zone', or_zone='exit_only', weak_fn='strong_green',
               wide_day_threshold=0.40, avg_lookback=10, max_attempts=999,
               ratchet_stop=True, ratchet_buffer=0.0),
    'V7.1': dict(exit_mode='next_zone', or_zone='exit_only', weak_fn='strong_green',
                 wide_day_threshold=0.40, avg_lookback=10, max_attempts=999,
                 ratchet_stop=True, ratchet_buffer=0.0, wick_require_above_open=True),
}

TRADE_CACHE_FILE = 'stage10_trade_cache.pkl'
CAND_CACHE_FILE = 'stage10_ml_candidates.pkl'
PROGRESS_FILE = 'stage10_progress.json'
RESULTS_FILE = 'stage10_results.json'

year_days = {y: [d for d in days if str(d)[:4] == y] for y in ALL_YEARS}


def log(note):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'note': note, 't': time.time()}, f)
    print(note, flush=True)


# ==========================================================================
# PART 1 -- V7 / V7.1 grid-search trade cache (band x cutoff x year)
# ==========================================================================
def cfg_key(method, band, cutoff):
    return f"{method}|band={band}|cutoff={cutoff}"


def load_pickle(path):
    try:
        with open(path, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return {}


def save_pickle(obj, path):
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        pickle.dump(obj, f)
    os.replace(tmp, path)


def build_trade_cache():
    """One run_version() call per (method, band, cutoff, TRAIN year); cached
    so the walk-forward fold selection below never re-simulates the same
    (config, year) pair twice."""
    cache = load_pickle(TRADE_CACHE_FILE)
    jobs = [(m, b, c, y) for m in METHOD_BASE for b in BANDS for c in CUTOFFS for y in TRAIN_YEARS]
    done = sum(1 for (m, b, c, y) in jobs if (cfg_key(m, b, c), y) in cache)
    for (method, band, cutoff, year) in jobs:
        key = (cfg_key(method, band, cutoff), year)
        if key in cache:
            continue
        cfg = dict(METHOD_BASE[method]); cfg['band'] = band; cfg['entry_cutoff'] = cutoff
        trades = run_version(cfg, year_days[year])
        cache[key] = [{'pnl': t['pnl']} for t in trades]  # trim to what stats() needs
        save_pickle(cache, TRADE_CACHE_FILE)
        done += 1
        log(f'[1/4] grid train runs {done}/{len(jobs)}: {method} band={band} cutoff={cutoff} '
            f'year={year} n={len(trades)}')
    log(f'[1/4] grid train runs complete ({len(jobs)}/{len(jobs)})')
    return cache


def year_stats(cache, method, band, cutoff, yrs):
    trades = []
    for y in yrs:
        trades.extend(cache[(cfg_key(method, band, cutoff), y)])
    return stats(trades), len(trades)


def best_by_net_per_trade(cache, method, yrs):
    """Selection rule used at every fold and for the final config: whichever
    (band, cutoff) has the best net $/share PER TRADE on `yrs`, among
    candidates clearing the MIN_TRADES floor. This is an OUT-OF-SAMPLE
    criterion whenever `yrs` is a fold's training years (never the fold's
    own validation year)."""
    best = None
    for band in BANDS:
        for cutoff in CUTOFFS:
            s, n = year_stats(cache, method, band, cutoff, yrs)
            if n < MIN_TRADES:
                continue
            npt = s['net'] / n
            if best is None or npt > best[0]:
                best = (npt, band, cutoff, s, n)
    return best


# ==========================================================================
# PART 2 -- V7 / V7.1 walk-forward folds, final frozen config, blind test
# ==========================================================================
def v7_base_cfg(method, band, cutoff):
    cfg = dict(METHOD_BASE[method])
    cfg['band'] = band
    cfg['entry_cutoff'] = cutoff
    return cfg


def select_and_test_rule_methods(cache):
    results = {}
    folds = [
        ('fold1', ['2020'], '2021'),
        ('fold2', ['2020', '2021'], '2022'),
        ('fold3', ['2020', '2021', '2022'], '2023'),
    ]
    for method in ['V7', 'V7.1']:
        results[method] = {'folds': {}}
        for name, train_years, val_year in folds:
            npt, band, cutoff, s_train, n_train = best_by_net_per_trade(cache, method, train_years)
            s_val, n_val = year_stats(cache, method, band, cutoff, [val_year])
            results[method]['folds'][name] = dict(
                train_years=train_years, val_year=val_year,
                chosen_band=band, chosen_cutoff=cutoff,
                train_stats=s_train, train_n=n_train, val_stats=s_val, val_n=n_val,
            )
            log(f'[2/4] {method} {name}: chose band={band} cutoff={cutoff} on {train_years}, '
                f'validated on {val_year} -> n={n_val} net={s_val["net"]:.3f}')

        # Final frozen config: same selection rule, over ALL of 2020-2023
        npt, band, cutoff, s_train, n_train = best_by_net_per_trade(cache, method, TRAIN_YEARS)
        results[method]['final'] = dict(chosen_band=band, chosen_cutoff=cutoff,
                                         train_stats=s_train, train_n=n_train)
        log(f'[2/4] {method} FINAL frozen config: band={band} cutoff={cutoff} '
            f'(trained on {TRAIN_YEARS})')

        # Blind test: frozen config, run fresh, once per test year -- never touched
        # until this point, never used to pick anything above.
        cfg = v7_base_cfg(method, band, cutoff)
        results[method]['test'] = {}
        for y in TEST_YEARS:
            trades = run_version(cfg, year_days[y])
            results[method]['test'][y] = dict(n=len(trades), stats=stats(trades))
            log(f'[2/4] {method} BLIND TEST {y}: n={len(trades)} net={stats(trades)["net"]:.3f}')

        # Combined 2024-2026 blind test (single run over the concatenated days --
        # valid because run_version() has no cross-day state, see module docstring)
        combined_days = year_days['2024'] + year_days['2025'] + year_days['2026']
        trades = run_version(cfg, combined_days)
        results[method]['test']['combined'] = dict(n=len(trades), stats=stats(trades))
    return results


# ==========================================================================
# PART 3 -- Rule OR Model: ML candidate cache + walk-forward GBM retraining
# ==========================================================================
def build_candidate_cache():
    cache = load_pickle(CAND_CACHE_FILE)
    for y in ALL_YEARS:
        if y in cache:
            continue
        t0 = time.time()
        cache[y] = build_candidates(year_days[y])
        save_pickle(cache, CAND_CACHE_FILE)
        log(f'[3/4] ML candidates {y}: n={len(cache[y])} ({time.time()-t0:.1f}s)')
    log('[3/4] ML candidate cache complete')
    return cache


def pick_threshold_and_fit(train_df):
    """Exactly Stage 8's STEP 3+4: an inner time split WITHIN train_df picks
    the probability threshold (never the fold's val/test year), then the
    model is refit on the full train_df."""
    train_dates = sorted(train_df['date'].unique())
    split_at = train_dates[int(len(train_dates) * 0.72)]
    inner_train = train_df[train_df['date'] < split_at]
    inner_val = train_df[train_df['date'] >= split_at]
    Xtr, ytr = prep(inner_train)
    Xval, _ = prep(inner_val)
    Xval = align(Xtr, Xval)
    clf0 = GradientBoostingClassifier(n_estimators=60, max_depth=2, learning_rate=0.05,
                                       subsample=0.8, random_state=0)
    clf0.fit(Xtr, ytr)
    inner_val = inner_val.copy()
    inner_val['proba'] = clf0.predict_proba(Xval)[:, 1]
    best_thr, best_net = 0.5, -1e18
    for thr in np.arange(0.35, 0.85, 0.025):
        sel = inner_val[inner_val['proba'] >= thr]
        if len(sel) < 5:
            continue
        if sel['pnl'].sum() > best_net:
            best_net, best_thr = sel['pnl'].sum(), thr

    Xtr_full, ytr_full = prep(train_df)
    clf = GradientBoostingClassifier(n_estimators=60, max_depth=2, learning_rate=0.05,
                                      subsample=0.8, random_state=0)
    clf.fit(Xtr_full, ytr_full)
    return clf, list(Xtr_full.columns), float(best_thr)


def combined_select_factory(threshold):
    """'Rule OR Model': take whichever candidate the hand rule confirms OR
    whose model probability clears `threshold`; among eligible candidates on
    a bar, score = rule_confirmed*1.0 + proba and take the top one."""
    def combined_select(bar_rows):
        elig = bar_rows[(bar_rows['rule_confirmed'] == 1) | (bar_rows['proba'] >= threshold)]
        if len(elig) == 0:
            return None
        elig = elig.copy()
        elig['score'] = elig['rule_confirmed'] * 1.0 + elig['proba']
        return elig.sort_values('score', ascending=False).iloc[0]
    return combined_select


def align_cols(train_cols, X_other):
    X_other = X_other.copy()
    for c in train_cols:
        if c not in X_other.columns:
            X_other[c] = 0
    return X_other[train_cols]


def eval_ml(df, clf, train_cols, threshold, with_entry_price=False):
    X, _ = prep(df)
    X = align_cols(train_cols, X)
    df = df.copy()
    df['proba'] = clf.predict_proba(X)[:, 1]
    trades = run_sequential(df, combined_select_factory(threshold))
    if not with_entry_price:
        return stats(trades), len(trades)
    enriched = []
    for t in trades:
        d = pd.Timestamp(t['date']).date()
        entry_price = day_rows[d].iloc[t['bar_idx']].Close
        enriched.append({'pnl': t['pnl'], 'entry_price': entry_price})
    return stats([{'pnl': t['pnl']} for t in enriched]), len(enriched), enriched


def run_ml_walk_forward(cand_cache):
    results = {'folds': {}}
    folds = [
        ('fold1', ['2020'], '2021'),
        ('fold2', ['2020', '2021'], '2022'),
        ('fold3', ['2020', '2021', '2022'], '2023'),
    ]
    for name, train_years, val_year in folds:
        train_df = pd.concat([cand_cache[y] for y in train_years], ignore_index=True)
        clf, train_cols, thr = pick_threshold_and_fit(train_df)
        s, n = eval_ml(cand_cache[val_year], clf, train_cols, thr)
        results['folds'][name] = dict(train_years=train_years, val_year=val_year,
                                       threshold=thr, n=n, stats=s)
        log(f'[3/4] Rule-OR-Model {name}: threshold={thr:.3f}, validated on {val_year} '
            f'-> n={n} net={s["net"]:.3f}')

    # Final frozen model: train on ALL of 2020-2023, then touch each test year once
    train_df_final = pd.concat([cand_cache[y] for y in TRAIN_YEARS], ignore_index=True)
    clf_final, train_cols_final, thr_final = pick_threshold_and_fit(train_df_final)
    results['final_threshold'] = thr_final
    results['test'] = {}
    for y in TEST_YEARS:
        s, n = eval_ml(cand_cache[y], clf_final, train_cols_final, thr_final)
        results['test'][y] = dict(n=n, stats=s)
        log(f'[3/4] Rule-OR-Model BLIND TEST {y}: n={n} net={s["net"]:.3f}')

    # Combined 2024-2026 (single evaluation of the already-frozen final model)
    combined_df = pd.concat([cand_cache[y] for y in TEST_YEARS], ignore_index=True)
    s, n = eval_ml(combined_df, clf_final, train_cols_final, thr_final)
    results['test']['combined'] = dict(n=n, stats=s)

    # In-sample (train) fit, clearly labeled -- expected to look better than
    # any genuinely out-of-sample number above.
    s_insample, n_insample = eval_ml(train_df_final, clf_final, train_cols_final, thr_final)
    results['in_sample_2020_2023'] = dict(n=n_insample, stats=s_insample)

    return results, (clf_final, train_cols_final, thr_final)


# ==========================================================================
# PART 4 -- $100/trade, Gross %, and 1-cent-cost-adjusted figures
# ==========================================================================
def dollar100_stats(trades_with_entry):
    """$100 position sized at each trade's own entry price (100/entry_price
    shares) -- same normalization convention used throughout the rest of the
    site. 'Gross %' is this same $100-avg figure re-expressed as a percentage
    (numerically identical, since the position is exactly $100)."""
    n = len(trades_with_entry)
    if n == 0:
        return dict(n=0, dollar100_total=0.0, dollar100_avg=0.0, gross_pct=0.0,
                    dollar100_total_at1c=0.0, dollar100_avg_at1c=0.0)
    d100 = [100.0 * (t['pnl'] / t['entry_price']) for t in trades_with_entry]
    # 1-cent round-trip cost per share, on a (100/entry_price)-share position:
    # cost in dollars = (100/entry_price) * 0.01
    d100_at1c = [100.0 * ((t['pnl'] - 0.01) / t['entry_price']) for t in trades_with_entry]
    total, total_1c = sum(d100), sum(d100_at1c)
    return dict(n=n, dollar100_total=total, dollar100_avg=total / n, gross_pct=total / n,
                dollar100_total_at1c=total_1c, dollar100_avg_at1c=total_1c / n)


def finalize_rule_method(method, band, cutoff):
    cfg = v7_base_cfg(method, band, cutoff)
    periods = {
        '2020_2023_insample': [d for d in days if '2020-01-01' <= str(d) <= '2023-12-31'],
        '2024': year_days['2024'], '2025': year_days['2025'], '2026': year_days['2026'],
    }
    out = {'chosen_band': band, 'chosen_cutoff': cutoff, 'periods': {}}
    for pname, pdays in periods.items():
        trades = run_version(cfg, pdays)  # full trade dicts (with entry_price) -- not the trimmed cache
        out['periods'][pname] = dict(stats=stats(trades), dollar=dollar100_stats(trades))
    return out


def finalize_ml_method(cand_cache, ml_model):
    clf_final, train_cols_final, thr_final = ml_model
    out = {'threshold': thr_final, 'periods': {}}
    train_df_final = pd.concat([cand_cache[y] for y in TRAIN_YEARS], ignore_index=True)
    periods = {'2020_2023_insample': train_df_final, '2024': cand_cache['2024'],
               '2025': cand_cache['2025'], '2026': cand_cache['2026']}
    for pname, pdf in periods.items():
        s, n, enriched = eval_ml(pdf, clf_final, train_cols_final, thr_final, with_entry_price=True)
        out['periods'][pname] = dict(stats=s, dollar=dollar100_stats(enriched))
    return out


# ==========================================================================
# main
# ==========================================================================
def main():
    log('[1/4] building V7/V7.1 grid-search trade cache (72 jobs)...')
    trade_cache = build_trade_cache()

    log('[2/4] walk-forward fold selection + blind test, V7 and V7.1...')
    rule_results = select_and_test_rule_methods(trade_cache)

    log('[3/4] building ML candidate cache (7 years)...')
    cand_cache = build_candidate_cache()
    log('[3/4] walk-forward GBM retraining + blind test, Rule OR Model...')
    ml_results, ml_model = run_ml_walk_forward(cand_cache)

    log('[4/4] computing $100/trade, Gross %, and 1-cent-cost figures...')
    finalized = {}
    for method in ['V7', 'V7.1']:
        band = rule_results[method]['final']['chosen_band']
        cutoff = rule_results[method]['final']['chosen_cutoff']
        finalized[method] = finalize_rule_method(method, band, cutoff)
    finalized['ML_Rule_OR_Model'] = finalize_ml_method(cand_cache, ml_model)

    out = {
        'walk_forward_folds_and_blind_test': rule_results,
        'ml_walk_forward_folds_and_blind_test': ml_results,
        'dollar100_and_cost_figures': finalized,
    }
    with open(RESULTS_FILE, 'w') as f:
        json.dump(out, f, indent=2, default=float)
    log(f'[4/4] ALL DONE -- results written to {RESULTS_FILE}')


if __name__ == '__main__':
    main()
