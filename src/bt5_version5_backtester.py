"""
CNQ 5-min zone strategy -- Version 5 backtester.
Rebuilt 2026-08-19 from 02_Core_Trade_Strategy_Rules.docx after the prior
session's V1-V4 script was lost (it lived only in ephemeral /tmp storage).
This is the reference implementation going forward -- see the "Process
Note" in 02_Core_Trade_Strategy_Rules.docx. Do not let this file become
ephemeral again: it is the ground truth for what "V4-rebuilt" and "V5"
actually did, not just the prose description in 05_Full_Test_Report.docx.

Known gap vs. the original V1-V4 script: the "second pullback" test used
to confirm INTRA_HIGH / INTRA_LOW zones (see build_day_index / the
intra_low_candidate / intra_high_candidate logic below) is this session's
own reasonable reading of a rule that was never given a precise numeric
definition in the strategy doc. It produces a similar but not always
identical zone list versus the historical V4 ledger. Tightening that
definition (in the strategy doc) and updating this function together is
flagged as the top priority before Version 6.

Usage: put the raw CSV (Datetime/Open/High/Low/Close/...) at ./cnq.csv
and run `python3 bt5_version5_backtester.py`. Prints a V4-rebuilt vs V5
summary and full trade ledgers for both.
"""
import pandas as pd
import numpy as np
import sys

BAND = 0.04
MAX_ATTEMPTS_PER_ZONE = 2

df = pd.read_csv('cnq.csv')
df['Datetime'] = pd.to_datetime(df['Datetime'])
df['date'] = df['Datetime'].dt.date
df['time'] = df['Datetime'].dt.strftime('%H:%M')
df = df.sort_values('Datetime').reset_index(drop=True)

def is_green(c):
    return c.Close > c.Open

def body(c):
    return abs(c.Close - c.Open)

def rng(c):
    return c.High - c.Low

def strong_green(c, avg_range, prev):
    if not is_green(c):
        return False
    r = rng(c)
    if r <= 0:
        return False
    b = body(c)
    if b < 0.6 * r:
        return False
    if r < avg_range:
        return False
    if (c.Close - c.Low) / r < 0.75:
        return False
    if prev is not None and not is_green(prev):
        if not (b > body(prev) or r > rng(prev)):
            return False
    return True

def long_lower_wick(c):
    b = body(c)
    lw = min(c.Open, c.Close) - c.Low
    if lw >= 2 * b and lw > 0:
        return True
    if r0 := rng(c):
        if r0 <= 0.05 and b <= 0.02:
            return True
    return False

class Zone:
    def __init__(self, kind, level, created_idx):
        self.kind = kind
        self.level = level
        self.created_idx = created_idx
    def band(self):
        return (self.level - BAND, self.level + BAND)
    def touched_by(self, c):
        lo, hi = self.band()
        return c.Low <= hi and c.High >= lo
    def key(self):
        return (self.kind, round(self.level, 2))

def build_day_index(df):
    days = list(df['date'].unique())
    day_rows = {d: df[df['date'] == d].reset_index(drop=True) for d in days}
    return days, day_rows

days, day_rows = build_day_index(df)

# prior-day H/L/C map
prior_hlc = {}
for i, d in enumerate(days):
    if i == 0:
        continue
    prev = day_rows[days[i-1]]
    prior_hlc[d] = (prev.High.max(), prev.Low.min(), prev.Close.iloc[-1])

TEST_DAYS = [d for d in days if str(d) >= '2026-08-07' and str(d) <= '2026-08-14']

def avg_range_lastN(rows, i, n=5):
    lo = max(0, i-n)
    if i == 0:
        return rng(rows.iloc[i])
    seg = rows.iloc[lo:i]
    if len(seg) == 0:
        return rng(rows.iloc[i])
    return seg.apply(lambda r: r.High - r.Low, axis=1).mean()

def run_version(weak_fn_name):
    """weak_fn_name: 'v4' -> not is_green ; 'v5' -> not strong_green"""
    trades = []
    skip_log = 0

    for d in TEST_DAYS:
        rows = day_rows[d]
        n = len(rows)
        if n == 0:
            continue
        zones = []
        zone_attempts = {}

        # prior day zones established at open
        if d in prior_hlc:
            ph, pl, pc = prior_hlc[d]
            zones.append(Zone('PDH', ph, 0))
            zones.append(Zone('PDL', pl, 0))
            zones.append(Zone('PDC', pc, 0))

        open_zone_added = False
        or_zone_added = False
        day_low_so_far = None
        day_high_so_far = None
        # simple swing tracking for INTRA_LOW / INTRA_HIGH:
        # candidate extreme -> confirmed zone on second touch/pullback within BAND after moving away by >= BAND*2
        intra_low_candidate = None
        intra_low_confirmed = False
        intra_high_candidate = None
        intra_high_confirmed = False
        moved_away_from_low = False
        moved_away_from_high = False

        position = None  # dict: entry_idx, entry_price, stop, tp, zone_key, breakeven

        for i in range(n):
            c = rows.iloc[i]
            t = c.time

            # Zone 1 (open) established at 09:30
            if t == '09:30' and not open_zone_added:
                zones.append(Zone('OPEN', c.Open, i))
                open_zone_added = True
                day_low_so_far = c.Low
                day_high_so_far = c.High

            # track day low/high for intraday zone candidates
            if day_low_so_far is None:
                day_low_so_far = c.Low
                day_high_so_far = c.High
            else:
                if c.Low < day_low_so_far:
                    day_low_so_far = c.Low
                    intra_low_candidate = c.Low
                    intra_low_confirmed = False
                    moved_away_from_low = False
                if c.High > day_high_so_far:
                    day_high_so_far = c.High
                    intra_high_candidate = c.High
                    intra_high_confirmed = False
                    moved_away_from_high = False

            # detect "moved away" then "second pullback" to confirm intraday zones
            if intra_low_candidate is not None and not intra_low_confirmed:
                if c.Low > intra_low_candidate + 2*BAND:
                    moved_away_from_low = True
                if moved_away_from_low and c.Low <= intra_low_candidate + BAND and t != '09:30':
                    intra_low_confirmed = True
                    zones.append(Zone('INTRA_LOW', intra_low_candidate, i))

            if intra_high_candidate is not None and not intra_high_confirmed:
                if c.High < intra_high_candidate - 2*BAND:
                    moved_away_from_high = True
                if moved_away_from_high and c.High >= intra_high_candidate - BAND:
                    intra_high_confirmed = True
                    zones.append(Zone('INTRA_HIGH', intra_high_candidate, i))

            # OR zone established at 09:45 from candles at 09:30/09:35/09:40
            if t == '09:45' and not or_zone_added:
                first3 = rows[rows['time'].isin(['09:30', '09:35', '09:40'])]
                if len(first3) == 3:
                    zones.append(Zone('OR_HIGH', first3.High.max(), i))
                    zones.append(Zone('OR_LOW', first3.Low.min(), i))
                or_zone_added = True

            prev_candle = rows.iloc[i-1] if i > 0 else None
            avg_rng = avg_range_lastN(rows, i, 5)

            # ---- manage open position ----
            if position is not None:
                exited = False
                # 1. hard stop
                stop_level = position['stop']
                if c.Low <= stop_level:
                    exit_price = stop_level
                    pnl = exit_price - position['entry_price']
                    trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                    'pnl': pnl, 'reason': 'Hard stop', 'date': d})
                    position = None
                    exited = True
                if not exited:
                    # 2. next zone reached with weak price action
                    for z in zones:
                        if z.created_idx <= i and z.level > position['entry_price'] + 1e-9:
                            if z.touched_by(c):
                                if weak_fn_name == 'v4':
                                    weak = not is_green(c)
                                else:
                                    weak = not strong_green(c, avg_rng, prev_candle)
                                if weak:
                                    exit_price = c.Close
                                    pnl = exit_price - position['entry_price']
                                    trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                                    'pnl': pnl, 'reason': 'Next zone, weak candle', 'date': d})
                                    position = None
                                    exited = True
                                break
                if not exited and position is not None:
                    # 3. TP floor backstop -- only if no established zone remains above entry
                    zones_above = [z for z in zones if z.created_idx <= i and z.level > position['entry_price'] + 1e-9]
                    if not zones_above and c.High >= position['tp']:
                        exit_price = position['tp']
                        pnl = exit_price - position['entry_price']
                        trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                        'pnl': pnl, 'reason': 'TP floor backstop', 'date': d})
                        position = None
                        exited = True
                if not exited and position is not None:
                    # 4. EOD flatten
                    if i == n - 1:
                        exit_price = c.Close
                        pnl = exit_price - position['entry_price']
                        trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                        'pnl': pnl, 'reason': 'EOD flatten', 'date': d})
                        position = None
                        exited = True
                if not exited and position is not None:
                    # breakeven stop update
                    if is_green(c) and c.Close > position['entry_price']:
                        position['stop'] = max(position['stop'], position['entry_price'])

            # ---- look for new entry ----
            if position is None and t != '09:30':
                # entry window 09:35-12:55 ET (documented default interpretation)
                if '09:35' <= t <= '12:55':
                    established = [z for z in zones if z.created_idx <= i]
                    touched = [z for z in established if z.touched_by(c)]
                    if touched:
                        levels_est = [z.level for z in established]
                        hod = rows.iloc[:i+1].High.max()
                        for z in touched:
                            zk = z.key()
                            attempts = zone_attempts.get(zk, 0)
                            if attempts >= MAX_ATTEMPTS_PER_ZONE:
                                skip_log += 1
                                continue
                            rank = 'HIGHEST' if z.level == max(levels_est) else ('LOWEST' if z.level == min(levels_est) else 'MEDIUM')
                            # first-low rule: skip if this is the very candle that just made a brand-new day low
                            # (i.e. zone confirmed same bar as candidate -- shouldn't happen given confirmation logic, but guard anyway)
                            sg = strong_green(c, avg_rng, prev_candle)
                            wick_ok = long_lower_wick(c) and z.kind in ('INTRA_LOW', 'OR_LOW', 'PDL', 'OPEN')
                            confirmed = sg or wick_ok
                            if not confirmed:
                                continue
                            if rank == 'HIGHEST' and not (c.Close > hod):
                                continue
                            zone_attempts[zk] = attempts + 1
                            is_wide = (day_high_so_far - day_low_so_far) >= 0.50
                            stop_off = 0.15 if is_wide else 0.10
                            tp_off = 0.30 if is_wide else 0.20
                            entry_price = c.Close
                            position = {
                                'entry_idx': i, 'entry_time': t, 'entry_price': entry_price,
                                'stop': entry_price - stop_off, 'tp': entry_price + tp_off,
                                'zone_kind': z.kind, 'zone_level': z.level, 'zone_rank': rank,
                                'attempt': zone_attempts[zk],
                            }
                            break

    return trades, skip_log

for label, fn in [('V4 (reimplementation baseline)', 'v4'), ('V5 (strong-signal exit refinement)', 'v5')]:
    trades, skips = run_version(fn)
    wins = [t for t in trades if t['pnl'] > 0.005]
    losses = [t for t in trades if t['pnl'] < -0.005]
    scratches = [t for t in trades if abs(t['pnl']) <= 0.005]
    net = sum(t['pnl'] for t in trades)
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = -sum(t['pnl'] for t in losses)
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')
    n = len(trades)
    print(f"\n=== {label} ===")
    print(f"Trades: {n}  Wins: {len(wins)}  Scratches: {len(scratches)}  Losses: {len(losses)}")
    if n:
        print(f"Win rate (all): {len(wins)/n*100:.1f}%  Win rate (excl scratch): {len(wins)/max(1,(len(wins)+len(losses)))*100:.1f}%")
    print(f"Net P&L: {net:+.3f}  Profit factor: {pf:.2f}")
    for t in trades:
        print(f"  {t['date']} {t['entry_time']}->{t['exit_time']}  {t['zone_kind']}({t['zone_rank']}) att{t['attempt']}  "
              f"entry={t['entry_price']:.2f} exit={t['exit_price']:.2f}  pnl={t['pnl']:+.3f}  [{t['reason']}]")
