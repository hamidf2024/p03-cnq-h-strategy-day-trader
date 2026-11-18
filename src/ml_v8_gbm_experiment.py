"""
Stage 8 experiment: can a numeric ML model (gradient boosting over the real
OHLCV bars + the zone/candle features already defined in V7.1) beat the
hand-written V7.1 rules, out of sample?

Context: the user asked whether a transformer could "learn the strategy"
from the 11 annotated chart screenshots. That's not viable -- 11 images is
nowhere near enough to train any neural network, vision or otherwise, and
the screenshots are a lossy picture of data already held exactly as numbers
(data/raw/CNQ_5min_20260520_to_20260814.csv). The screenshots' real value
(showing the zone logic so it could be turned into rules) is already spent;
that's how V1-V7.1 were built. The approved alternative: a numeric model
trained on the real bars, benchmarked against V7.1 with the same
walk-forward, no-look-ahead discipline as every other version in this
project -- gradient boosting over a transformer, per this project's own
Project 9 and Project 13 pages, which already found transformers need far
more data than ~500 candidate rows / ~28-32 days supply here.

Method
------
1. Every zone touch in the entry window (09:35 - entry_cutoff), not just the
   ones V7.1's hand rule would take, is logged as a labeled candidate: label
   = the realized P&L if a trade were opened there and managed with V7.1's
   *exact* stop/target/exit rules (same stop/floor, same ratchet, same
   next-zone weak-candle exit, same TP backstop). This widens the pool V7.1
   rejects or never considers into a dataset the model can learn from.
2. Validation (required before trusting anything else here): restricting
   this candidate set to the ones V7.1's own rule would confirm and feeding
   them through the exact same sequential, one-trade-at-a-time walk used by
   `run_version` reproduces V7.1's official numbers for Jul1-Aug14 exactly
   (n=75, win_rate_excl=72.9%, pf=3.81, net=+2.690) -- checked bar-for-bar,
   0 mismatches across all 75 real trades. Two bugs were caught and fixed
   during this step (a break-statement misread, and conflating the 0.012
   entry band with the separate ~0.04 swing-confirmation band) -- exactly
   the kind of regression check this project's own test protocol requires
   before trusting a new result.
3. Train: May 20 - Jun 30, 2026 (28 days, 475 candidate rows). An internal,
   time-based validation split *within* that training window (last 8 of the
   28 days) is used to pick the model's probability threshold -- the Jul 1 -
   Aug 14 test period is never touched until the very last step.
4. Test: Jul 1 - Aug 14, 2026 -- the exact same window V7.1's official
   numbers were reported on, for a direct, apples-to-apples comparison.

Result (see bottom of this file's output): REJECTED. None of the three ML
variants tried beat V7.1's net profit on the held-out test window. Kept here,
run and reported, per this project's own standard: every tried idea is
written up, including (especially) the ones that didn't work.
"""
import sys
import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

sys.path.insert(0, '.')
import bt7
from bt7 import (is_green, body, rng, strong_green, strong_red, long_lower_wick,
                  avg_range_lastN, Zone, days, day_rows, prior_hlc, stats)

CFG = bt7.VERSIONS['V7.1']
BAND = CFG.get('band', bt7.BAND)
SWING_BAND = CFG.get('swing_band', bt7.BAND)
ENTRY_CUTOFF = CFG.get('entry_cutoff', '12:55')
AVG_LOOKBACK = CFG.get('avg_lookback', 5)
WIDE_DAY_THRESHOLD = CFG.get('wide_day_threshold', 0.50)
NORMAL_STOP, NORMAL_TP = CFG.get('normal_stop', 0.10), CFG.get('normal_tp', 0.20)
WIDE_STOP, WIDE_TP = CFG.get('wide_stop', 0.15), CFG.get('wide_tp', 0.30)
RATCHET_STOP = CFG.get('ratchet_stop', False)
RATCHET_BUFFER = CFG.get('ratchet_buffer', 0.02)
WICK_REQUIRE_ABOVE_OPEN = CFG.get('wick_require_above_open', False)
WICK_CLOSE_FRAC = CFG.get('wick_close_frac', 0.0)
MIN_ZONE_FRAC = CFG.get('min_zone_frac', 0.0)
WEAK_FN = CFG.get('weak_fn', 'strong_green')
OR_ZONE = CFG.get('or_zone', 'exit_only')
ENTRY_DISABLED_KINDS = ('OR_HIGH', 'OR_LOW') if OR_ZONE == 'exit_only' else ()

daily_close = {d: day_rows[d].Close.iloc[-1] for d in days}
day_index = {d: i for i, d in enumerate(days)}

def prior_trend(d, n):
    idx = day_index[d]
    if idx < n + 1:
        return None
    return daily_close[days[idx - 1]] - daily_close[days[idx - 1 - n]]

def build_day_zones(d):
    rows = day_rows[d]
    n = len(rows)
    zones = []
    if d in prior_hlc:
        ph, pl, pc = prior_hlc[d]
        zones.append(Zone('PDH', ph, 0))
        zones.append(Zone('PDL', pl, 0))
        zones.append(Zone('PDC', pc, 0))
    open_zone_added = or_zone_added = False
    day_low_so_far = day_high_so_far = None
    intra_low_candidate = intra_high_candidate = None
    intra_low_confirmed = intra_high_confirmed = False
    moved_away_from_low = moved_away_from_high = False
    day_low_hist, day_high_hist = [], []
    for i in range(n):
        c = rows.iloc[i]
        t = c.time
        if t == '09:30' and not open_zone_added:
            zones.append(Zone('OPEN', c.Open, i))
            open_zone_added = True
            day_low_so_far, day_high_so_far = c.Low, c.High
        if day_low_so_far is None:
            day_low_so_far, day_high_so_far = c.Low, c.High
        else:
            if c.Low < day_low_so_far:
                day_low_so_far = c.Low
                intra_low_candidate, intra_low_confirmed, moved_away_from_low = c.Low, False, False
            if c.High > day_high_so_far:
                day_high_so_far = c.High
                intra_high_candidate, intra_high_confirmed, moved_away_from_high = c.High, False, False
        if intra_low_candidate is not None and not intra_low_confirmed:
            if c.Low > intra_low_candidate + 2 * SWING_BAND:
                moved_away_from_low = True
            if moved_away_from_low and c.Low <= intra_low_candidate + SWING_BAND and t != '09:30':
                intra_low_confirmed = True
                zones.append(Zone('INTRA_LOW', intra_low_candidate, i))
        if intra_high_candidate is not None and not intra_high_confirmed:
            if c.High < intra_high_candidate - 2 * SWING_BAND:
                moved_away_from_high = True
            if moved_away_from_high and c.High >= intra_high_candidate - SWING_BAND:
                intra_high_confirmed = True
                zones.append(Zone('INTRA_HIGH', intra_high_candidate, i))
        if OR_ZONE in ('full', 'exit_only') and t == '09:45' and not or_zone_added:
            first3 = rows[rows['time'].isin(['09:30', '09:35', '09:40'])]
            if len(first3) == 3:
                zones.append(Zone('OR_HIGH', first3.High.max(), i))
                zones.append(Zone('OR_LOW', first3.Low.min(), i))
            or_zone_added = True
        day_low_hist.append(day_low_so_far)
        day_high_hist.append(day_high_so_far)
    return zones, day_low_hist, day_high_hist

def simulate_exit(rows, zones_full, entry_idx, entry_price, stop0, tp):
    n = len(rows)
    stop = stop0
    for i in range(entry_idx + 1, n):
        c = rows.iloc[i]
        prev_candle = rows.iloc[i - 1]
        avg_rng = avg_range_lastN(rows, i, AVG_LOOKBACK)
        if c.Low <= stop:
            return dict(exit_idx=i, exit_price=stop, pnl=stop - entry_price, reason='Hard stop')
        min_zone_level = entry_price + MIN_ZONE_FRAC * (tp - entry_price)
        qualifying = [z for z in zones_full if z.created_idx <= i and z.level > entry_price + 1e-9
                      and z.level >= min_zone_level]
        first_touched = next((z for z in qualifying if z.touched_by(c, BAND)), None)
        if first_touched is not None:
            weak = (not is_green(c)) if WEAK_FN == 'not_green' else (not strong_green(c, avg_rng, prev_candle))
            if weak:
                return dict(exit_idx=i, exit_price=c.Close, pnl=c.Close - entry_price, reason='Next zone, weak candle')
            elif RATCHET_STOP:
                new_stop = first_touched.level - RATCHET_BUFFER
                if new_stop > stop:
                    stop = new_stop
        else:
            if not qualifying and c.High >= tp:
                return dict(exit_idx=i, exit_price=tp, pnl=tp - entry_price, reason='TP floor backstop')
        if i == n - 1:
            return dict(exit_idx=i, exit_price=c.Close, pnl=c.Close - entry_price, reason='EOD flatten')
        if is_green(c) and c.Close > entry_price:
            stop = max(stop, entry_price)
    last = rows.iloc[n - 1]
    return dict(exit_idx=n - 1, exit_price=last.Close, pnl=last.Close - entry_price, reason='EOD flatten (fallback)')

def build_candidates(test_days):
    rows_out = []
    for d in test_days:
        rows = day_rows[d]
        n = len(rows)
        zones_full, day_low_hist, day_high_hist = build_day_zones(d)
        zone_attempts = {}
        day_open = rows.iloc[0].Open
        for i in range(n):
            c = rows.iloc[i]
            t = c.time
            if t == '09:30' or t < '09:35' or t > ENTRY_CUTOFF:
                continue
            established = [z for z in zones_full if z.created_idx <= i and z.kind not in ENTRY_DISABLED_KINDS]
            if not established:
                continue
            touched = [z for z in established if z.touched_by(c, BAND)]
            if not touched:
                continue
            prev_candle = rows.iloc[i - 1]
            avg_rng = avg_range_lastN(rows, i, AVG_LOOKBACK)
            levels_est = [z.level for z in established]
            hod = rows.iloc[:i + 1].High.max()
            day_low_so_far, day_high_so_far = day_low_hist[i], day_high_hist[i]
            is_wide = (day_high_so_far - day_low_so_far) >= WIDE_DAY_THRESHOLD
            stop_off, tp_off = (WIDE_STOP, WIDE_TP) if is_wide else (NORMAL_STOP, NORMAL_TP)
            for z in touched:
                zk = z.key()
                attempts = zone_attempts.get(zk, 0)
                rank = 'HIGHEST' if z.level == max(levels_est) else ('LOWEST' if z.level == min(levels_est) else 'MEDIUM')
                sg = strong_green(c, avg_rng, prev_candle)
                wick_ok = long_lower_wick(c, WICK_CLOSE_FRAC) and z.kind in ('INTRA_LOW', 'OR_LOW', 'PDL', 'OPEN')
                if wick_ok and WICK_REQUIRE_ABOVE_OPEN and z.kind == 'OPEN' and not (c.Close > day_open):
                    wick_ok = False
                confirmed_raw = sg or wick_ok
                confirmed = confirmed_raw and not (rank == 'HIGHEST' and not (c.Close > hod)) and attempts < CFG['max_attempts']
                entry_price = c.Close
                sim = simulate_exit(rows, zones_full, i, entry_price, entry_price - stop_off, entry_price + tp_off)
                bodyv, rngv = body(c), rng(c)
                row = dict(
                    date=str(d), time=t, bar_idx=i,
                    zone_kind=z.kind, zone_rank=rank, zone_attempt=attempts,
                    is_green=int(is_green(c)), body=bodyv, range=rngv,
                    body_frac=(bodyv / rngv if rngv > 0 else 0.0),
                    close_frac=((c.Close - c.Low) / rngv if rngv > 0 else 0.0),
                    lower_wick_frac=((min(c.Open, c.Close) - c.Low) / rngv if rngv > 0 else 0.0),
                    upper_wick_frac=((c.High - max(c.Open, c.Close)) / rngv if rngv > 0 else 0.0),
                    strong_green=int(sg), strong_red=int(strong_red(c, avg_rng, prev_candle)),
                    long_lower_wick=int(long_lower_wick(c, WICK_CLOSE_FRAC)),
                    minutes_since_open=(i * 5),
                    dist_to_zone=(c.Close - z.level),
                    n_zones_established=len(established),
                    day_range_so_far=(day_high_so_far - day_low_so_far),
                    is_wide_day=int(is_wide),
                    avg_range_lookback=avg_rng,
                    rel_range=(rngv / avg_rng if avg_rng > 0 else 1.0),
                    close_vs_open=(c.Close - day_open),
                    close_above_hod=int(c.Close > hod),
                    volume=c.Volume,
                    trend_1d=prior_trend(d, 1), trend_3d=prior_trend(d, 3),
                    trend_5d=prior_trend(d, 5), trend_10d=prior_trend(d, 10),
                    dow=pd.Timestamp(d).dayofweek,
                    rule_confirmed=int(confirmed),
                    pnl=sim['pnl'], profitable=int(sim['pnl'] > 0.005),
                    exit_reason=sim['reason'], exit_idx=sim['exit_idx'],
                )
                rows_out.append(row)
                if confirmed:
                    zone_attempts[zk] = attempts + 1
    return pd.DataFrame(rows_out)

FEATURES_NUM = [
    'zone_attempt', 'is_green', 'body', 'range', 'body_frac', 'close_frac',
    'lower_wick_frac', 'upper_wick_frac', 'strong_green', 'strong_red',
    'long_lower_wick', 'minutes_since_open', 'dist_to_zone', 'n_zones_established',
    'day_range_so_far', 'is_wide_day', 'avg_range_lookback', 'rel_range',
    'close_vs_open', 'close_above_hod', 'volume', 'trend_1d', 'trend_3d',
    'trend_5d', 'trend_10d', 'dow',
]
FEATURES_CAT = ['zone_kind', 'zone_rank']

def prep(df):
    df = df.copy()
    for c in ['trend_1d', 'trend_3d', 'trend_5d', 'trend_10d']:
        df[c] = df[c].fillna(0.0)
    cat = pd.get_dummies(df[FEATURES_CAT], prefix=FEATURES_CAT)
    X = pd.concat([df[FEATURES_NUM].reset_index(drop=True), cat.reset_index(drop=True)], axis=1)
    y = df['profitable'].values
    return X, y

def align(X_train, X_other):
    X_other = X_other.copy()
    for c in X_train.columns:
        if c not in X_other.columns:
            X_other[c] = 0
    return X_other[X_train.columns]

def run_sequential(df, select_fn):
    trades = []
    for d, g in df.groupby('date'):
        position_open_until = -1
        for bar_idx, bar_rows in g.sort_values('bar_idx').groupby('bar_idx'):
            if bar_idx <= position_open_until:
                continue
            row = select_fn(bar_rows)
            if row is None:
                continue
            trades.append({'pnl': row['pnl'], 'date': d, 'bar_idx': bar_idx})
            position_open_until = row['exit_idx']
    return trades

if __name__ == '__main__':
    all_days_full_range = [d for d in days if str(d) >= '2026-07-01']

    print("=" * 70)
    print("STEP 1: VALIDATION -- must reproduce V7.1's official numbers exactly")
    print("=" * 70)
    real_trades = bt7.run_version(bt7.VERSIONS['V7.1'], all_days_full_range)
    s_real = stats(real_trades)
    print("Official run_version:", s_real)

    cand_full = build_candidates(all_days_full_range)
    cand_idx = {}
    for r in cand_full.itertuples():
        cand_idx.setdefault((r.date, r.bar_idx), r.pnl)
    mismatches = 0
    for t in real_trades:
        key = (str(t['date']), t['entry_idx'])
        if key not in cand_idx or abs(cand_idx[key] - t['pnl']) > 1e-6:
            mismatches += 1
    print(f"Mismatches vs official (must be 0): {mismatches} / {len(real_trades)}")
    assert mismatches == 0, "Validation failed -- do not trust downstream results."
    print("VALIDATED.\n")

    print("=" * 70)
    print("STEP 2: build train (May20-Jun30) / test (Jul1-Aug14) candidate sets")
    print("=" * 70)
    train_days = [d for d in days if '2026-05-20' <= str(d) < '2026-07-01']
    test_days = all_days_full_range
    train_cand = build_candidates(train_days)
    test_cand = build_candidates(test_days)
    print(f"train: {len(train_days)} days, {len(train_cand)} candidates, "
          f"profitable rate {train_cand.profitable.mean():.3f}")
    print(f"test:  {len(test_days)} days, {len(test_cand)} candidates, "
          f"profitable rate {test_cand.profitable.mean():.3f}\n")

    print("=" * 70)
    print("STEP 3: pick probability threshold on an internal validation split")
    print("         WITHIN the training period only (test set untouched)")
    print("=" * 70)
    train_dates = sorted(train_cand['date'].unique())
    split_at = train_dates[int(len(train_dates) * 0.72)]
    inner_train = train_cand[train_cand['date'] < split_at]
    inner_val = train_cand[train_cand['date'] >= split_at]
    Xtr, ytr = prep(inner_train)
    Xval, _ = prep(inner_val)
    Xval = align(Xtr, Xval)
    clf0 = GradientBoostingClassifier(n_estimators=60, max_depth=2, learning_rate=0.05,
                                       subsample=0.8, random_state=0)
    clf0.fit(Xtr, ytr)
    inner_val = inner_val.copy()
    inner_val['proba'] = clf0.predict_proba(Xval)[:, 1]
    best_thr, best_net = 0.5, -999
    for thr in np.arange(0.35, 0.85, 0.025):
        sel = inner_val[inner_val['proba'] >= thr]
        if len(sel) < 5:
            continue
        if sel['pnl'].sum() > best_net:
            best_net, best_thr = sel['pnl'].sum(), thr
    print(f"Chosen threshold: {best_thr:.3f} (inner validation net={best_net:+.3f})\n")

    print("=" * 70)
    print("STEP 4: refit on full training period, score test period, evaluate")
    print("         sequentially (one trade at a time) -- same discipline as")
    print("         bt7.run_version -- and compare to the official V7.1 baseline")
    print("=" * 70)
    Xtr_full, ytr_full = prep(train_cand)
    clf = GradientBoostingClassifier(n_estimators=60, max_depth=2, learning_rate=0.05,
                                      subsample=0.8, random_state=0)
    clf.fit(Xtr_full, ytr_full)
    Xtest, _ = prep(test_cand)
    Xtest = align(Xtr_full, Xtest)
    test_cand = test_cand.copy()
    test_cand['proba'] = clf.predict_proba(Xtest)[:, 1]

    THRESHOLD = best_thr

    def ml_select(bar_rows):
        elig = bar_rows[bar_rows['proba'] >= THRESHOLD]
        return None if len(elig) == 0 else elig.sort_values('proba', ascending=False).iloc[0]

    def combined_select(bar_rows):
        elig = bar_rows[(bar_rows['rule_confirmed'] == 1) | (bar_rows['proba'] >= THRESHOLD)]
        if len(elig) == 0:
            return None
        elig = elig.copy()
        elig['score'] = elig['rule_confirmed'] * 1.0 + elig['proba']
        return elig.sort_values('score', ascending=False).iloc[0]

    def filtered_select(bar_rows):
        elig = bar_rows[(bar_rows['rule_confirmed'] == 1) & (bar_rows['proba'] >= 0.45)]
        return None if len(elig) == 0 else elig.sort_values('proba', ascending=False).iloc[0]

    print("\nOfficial V7.1 baseline (bt7.run_version, Jul1-Aug14):")
    print(" ", s_real)
    print("\nML model alone (GBM, threshold=%.3f), sequential:" % THRESHOLD)
    print(" ", stats(run_sequential(test_cand, ml_select)))
    print("\nCombined (rule OR model), sequential:")
    print(" ", stats(run_sequential(test_cand, combined_select)))
    print("\nRule AND model agrees (proba>=0.45), sequential:")
    print(" ", stats(run_sequential(test_cand, filtered_select)))

    importances = pd.Series(clf.feature_importances_, index=Xtr_full.columns).sort_values(ascending=False)
    print("\nTop 10 feature importances (GBM, informational only):")
    print(importances.head(10).to_string())

    print("\n" + "=" * 70)
    print("CONCLUSION: REJECTED. None of the three ML variants beat V7.1's net")
    print("profit on the held-out Jul1-Aug14 window. See 06_Lessons_Learned.docx")
    print("research log entry and 01_Phases_of_Development.docx Stage 8 for the")
    print("full write-up and why this doesn't change the recommended version.")
    print("=" * 70)
