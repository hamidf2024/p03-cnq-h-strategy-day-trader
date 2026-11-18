"""
CNQ 5-min zone-trading strategy -- unified, parameterized backtester.

Covers Versions 1 through 7.1 as config presets in the VERSIONS dict below,
so every version can be run consistently across any date range rather than
only the narrow window it was originally tested on. Built by generalizing
bt6_version6_backtester.py.

Version 7 is the "Target P&L net and Win Rate" tuned configuration (selected
on Jul27-Aug14 only). Version 7.1 adds the root-cause fix for V7's
out-of-sample win-rate gap: a wick-confirmed bounce off the OPEN zone that
never closes back above the day's own open is rejected as an entry (PDL and
INTRA_LOW wick entries are unaffected -- they don't have this problem).
V7.1 is the current recommended live configuration as of 2026-08-19.

Several REJECTED_* presets are also kept, purely so the negative findings
written up in 06_Lessons_Learned.docx (curve-fitting to individual trades,
caught and rejected during the V7 tuning cycle) stay reproducible -- they
are not recommendations.

See 02_Core_Trade_Strategy_Rules.docx (rule definitions), 05_Full_Test_
Report.docx (full results, all versions, week-by-week), and 06_Lessons_
Learned.docx (research log, one entry per rule change, including every
rejected experiment and why) for full context behind each version.

Usage: put the raw CSV (Datetime/Open/High/Low/Close/...) at ./cnq.csv,
alongside this file, then either import it:

    from bt7 import VERSIONS, run_version, stats, days
    all_days = [d for d in days if str(d) >= '2026-07-01']
    trades = run_version(VERSIONS['V7.1'], all_days)
    print(stats(trades))

...or run it directly (`python3 bt7.py`) -- see the `if __name__ ==
'__main__':` block at the bottom, which prints every version's results,
week by week, over Jul 1 - Aug 14 (whatever range is in the CSV).

Known gap (inherited from V5/V6, still unresolved): the "second pullback"
test for INTRA_HIGH/INTRA_LOW zone confirmation has no precise numeric
definition in the strategy doc -- this is this project's own reasonable
reading of a qualitative rule, not something derived from real trades.
"""
import pandas as pd
import numpy as np

BAND = 0.04

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

def strong_red(c, avg_range, prev):
    """Symmetric mirror of strong_green, for a decisive reversal candle."""
    if is_green(c):
        return False
    r = rng(c)
    if r <= 0:
        return False
    b = body(c)
    if b < 0.6 * r:
        return False
    if r < avg_range:
        return False
    if (c.High - c.Close) / r < 0.75:
        return False
    return True

def long_lower_wick(c, close_frac_min=0.0):
    """A candle with a long lower wick, read as "price was rejected off the
    low and buyers held it." close_frac_min (0 = old/default behavior,
    unchanged for V1-V6) additionally requires the candle to actually CLOSE
    in the upper close_frac_min share of its own range -- i.e. the rejection
    has to show up as a real reclaim, not just a lower wick with a weak
    close. Without this, a candle that wicks down, tries to bounce, and
    then closes back near its low still counts as a valid "rejection," which
    is the root cause identified for Version 7's poor out-of-sample win rate
    in early/mid July: the wick-only check has no requirement that the
    candle actually closed strong, so it fires on failed-bounce candles in
    choppier weeks just as readily as on real reversals in trending weeks.
    """
    b = body(c)
    r0 = rng(c)
    lw = min(c.Open, c.Close) - c.Low
    close_frac = (c.Close - c.Low) / r0 if r0 > 0 else 0.0
    if lw >= 2 * b and lw > 0:
        if close_frac_min and close_frac < close_frac_min:
            return False
        return True
    if r0 and r0 <= 0.05 and b <= 0.02:
        if close_frac_min and close_frac < close_frac_min:
            return False
        return True
    return False

class Zone:
    def __init__(self, kind, level, created_idx):
        self.kind = kind
        self.level = level
        self.created_idx = created_idx
    def band(self, half_width=None):
        hw = BAND if half_width is None else half_width
        return (self.level - hw, self.level + hw)
    def touched_by(self, c, half_width=None):
        lo, hi = self.band(half_width)
        return c.Low <= hi and c.High >= lo
    def key(self):
        return (self.kind, round(self.level, 2))

days = list(df['date'].unique())
day_rows = {d: df[df['date'] == d].reset_index(drop=True) for d in days}

prior_hlc = {}
for i, d in enumerate(days):
    if i == 0:
        continue
    prev = day_rows[days[i-1]]
    prior_hlc[d] = (prev.High.max(), prev.Low.min(), prev.Close.iloc[-1])

def avg_range_lastN(rows, i, n):
    lo = max(0, i-n)
    if i == 0:
        return rng(rows.iloc[i])
    seg = rows.iloc[lo:i]
    if len(seg) == 0:
        return rng(rows.iloc[i])
    return seg.apply(lambda r: r.High - r.Low, axis=1).mean()

# ---- version presets ----
VERSIONS = {
    'V1': dict(exit_mode='tp_immediate', or_zone='off',       max_attempts=float('inf'), weak_fn='not_green'),
    'V2': dict(exit_mode='next_zone',    or_zone='off',       max_attempts=float('inf'), weak_fn='not_green'),
    'V3': dict(exit_mode='next_zone',    or_zone='full',      max_attempts=float('inf'), weak_fn='not_green'),
    'V4': dict(exit_mode='next_zone',    or_zone='full',      max_attempts=2,            weak_fn='not_green'),
    'V5': dict(exit_mode='next_zone',    or_zone='full',      max_attempts=2,            weak_fn='strong_green'),
    'V6': dict(exit_mode='next_zone',    or_zone='exit_only', max_attempts=2,            weak_fn='strong_green'),
    # V7: the "Target P&L net and Win Rate" tuned configuration. Selected on
    # the Jul27-Aug14 (3-week) window only; see 05_Full_Test_Report.docx and
    # 06_Lessons_Learned.docx for the full tuning history and every rejected
    # variant (curve-fit ones explicitly flagged there, not silently dropped).
    'V7': dict(exit_mode='next_zone', or_zone='exit_only', weak_fn='strong_green',
               band=0.012, wide_day_threshold=0.40, entry_cutoff='13:55', avg_lookback=10,
               max_attempts=999, ratchet_stop=True, ratchet_buffer=0.0),
    # V7.1: V7 plus the root-cause fix for V7's out-of-sample win-rate gap
    # (OPEN-zone wick-confirmed entries must close back above today's open).
    # Current recommended live configuration as of 2026-08-19.
    'V7.1': dict(exit_mode='next_zone', or_zone='exit_only', weak_fn='strong_green',
                 band=0.012, wide_day_threshold=0.40, entry_cutoff='13:55', avg_lookback=10,
                 max_attempts=999, ratchet_stop=True, ratchet_buffer=0.0,
                 wick_require_above_open=True),
    # Rejected during the V7 cycle -- kept here only so the negative results in
    # 06_Lessons_Learned.docx are reproducible, not as recommended presets.
    'REJECTED_min_zone_frac_0.5': dict(exit_mode='next_zone', or_zone='exit_only', max_attempts=2, weak_fn='strong_green', min_zone_frac=0.5),
    'REJECTED_min_zone_frac_1.0': dict(exit_mode='next_zone', or_zone='exit_only', max_attempts=2, weak_fn='strong_green', min_zone_frac=1.0),
    'REJECTED_2bar_confirm': dict(exit_mode='next_zone', or_zone='exit_only', max_attempts=2, weak_fn='strong_green', confirm_bars=2),
}

def run_version(cfg, test_days):
    trades = []
    max_attempts = cfg['max_attempts']
    or_zone = cfg['or_zone']  # 'off' | 'full' | 'exit_only'
    exit_mode = cfg['exit_mode']  # 'tp_immediate' | 'next_zone'
    weak_fn = cfg['weak_fn']  # 'not_green' | 'strong_green'
    # min_zone_frac: how far (as a fraction of entry->TP distance) a zone must be
    # before the "weak price action" exit check applies to it at all. 0 = current
    # V6 behavior (any zone above entry can trigger an early exit). 1.0 = only
    # zones at/beyond the nominal TP level can trigger it; below that, only the
    # hard stop can end the trade -- ride minor zones through on momentum.
    min_zone_frac = cfg.get('min_zone_frac', 0.0)
    # confirm_bars: 1 = current V6 behavior (a single weak candle at an
    # eligible zone exits immediately). 2 = require the weakness to persist
    # a second candle (or be an outright strong-red reversal, which exits
    # immediately either way) before confirming the exit -- grounded in two
    # separate real-trade annotations ("couple bars without strong signal",
    # "two strong red bar signal").
    confirm_bars = cfg.get('confirm_bars', 1)
    wide_day_threshold = cfg.get('wide_day_threshold', 0.50)
    entry_cutoff = cfg.get('entry_cutoff', '12:55')
    band = cfg.get('band', BAND)
    exclude_ranks = cfg.get('exclude_ranks', ())
    avg_lookback = cfg.get('avg_lookback', 5)
    ratchet_stop = cfg.get('ratchet_stop', False)
    ratchet_buffer = cfg.get('ratchet_buffer', 0.02)
    swing_band = cfg.get('swing_band', BAND)
    # ratchet_gate_exit: once the ratchet has already moved the stop into
    # profit (de-risked the trade for real, via a confirmed strong-candle
    # zone clearance -- not just "price is near TP"), suppress the
    # weak-candle exit and let the (now-raised) hard stop / next-zone / TP
    # backstop manage the rest. Structurally different from the three
    # already-rejected "let winners run" attempts: those relaxed the exit
    # unconditionally or on price-proximity; this only relaxes it after the
    # position has already banked a real, ratchet-confirmed profit floor.
    ratchet_gate_exit = cfg.get('ratchet_gate_exit', False)
    # Stop/target offsets. Defaults (0.10/0.20 normal, 0.15/0.30 wide) are the
    # real-trade-confirmed values used in every version through V6. Overriding
    # these is a materially bigger departure than the other tuned knobs above
    # -- it changes the strategy's actual risk definition, not just when/how
    # it exits -- so any run using non-default values here must be flagged
    # explicitly as such when reported.
    normal_stop = cfg.get('normal_stop', 0.10)
    normal_tp = cfg.get('normal_tp', 0.20)
    wide_stop = cfg.get('wide_stop', 0.15)
    wide_tp = cfg.get('wide_tp', 0.30)
    # Root-cause fix for V7's July out-of-sample win-rate collapse: require
    # the wick-confirmed entry candle to actually close strong (see
    # long_lower_wick's docstring). 0.0 = old behavior, unchanged for V1-V6.
    wick_close_frac = cfg.get('wick_close_frac', 0.0)
    wick_require_above_open = cfg.get('wick_require_above_open', False)
    entry_disabled_kinds = ('OR_HIGH', 'OR_LOW') if or_zone == 'exit_only' else ()
    or_enabled = or_zone in ('full', 'exit_only')

    for d in test_days:
        rows = day_rows[d]
        n = len(rows)
        if n == 0:
            continue
        zones = []
        zone_attempts = {}

        if d in prior_hlc:
            ph, pl, pc = prior_hlc[d]
            zones.append(Zone('PDH', ph, 0))
            zones.append(Zone('PDL', pl, 0))
            zones.append(Zone('PDC', pc, 0))

        open_zone_added = False
        or_zone_added = False
        day_low_so_far = None
        day_high_so_far = None
        intra_low_candidate = None
        intra_low_confirmed = False
        intra_high_candidate = None
        intra_high_confirmed = False
        moved_away_from_low = False
        moved_away_from_high = False

        position = None

        for i in range(n):
            c = rows.iloc[i]
            t = c.time

            if t == '09:30' and not open_zone_added:
                zones.append(Zone('OPEN', c.Open, i))
                open_zone_added = True
                day_low_so_far = c.Low
                day_high_so_far = c.High

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

            if intra_low_candidate is not None and not intra_low_confirmed:
                if c.Low > intra_low_candidate + 2*swing_band:
                    moved_away_from_low = True
                if moved_away_from_low and c.Low <= intra_low_candidate + swing_band and t != '09:30':
                    intra_low_confirmed = True
                    zones.append(Zone('INTRA_LOW', intra_low_candidate, i))

            if intra_high_candidate is not None and not intra_high_confirmed:
                if c.High < intra_high_candidate - 2*swing_band:
                    moved_away_from_high = True
                if moved_away_from_high and c.High >= intra_high_candidate - swing_band:
                    intra_high_confirmed = True
                    zones.append(Zone('INTRA_HIGH', intra_high_candidate, i))

            if or_enabled and t == '09:45' and not or_zone_added:
                first3 = rows[rows['time'].isin(['09:30', '09:35', '09:40'])]
                if len(first3) == 3:
                    zones.append(Zone('OR_HIGH', first3.High.max(), i))
                    zones.append(Zone('OR_LOW', first3.Low.min(), i))
                or_zone_added = True

            prev_candle = rows.iloc[i-1] if i > 0 else None
            avg_rng = avg_range_lastN(rows, i, avg_lookback)

            # ---- manage open position ----
            if position is not None:
                exited = False
                stop_level = position['stop']
                if c.Low <= stop_level:
                    exit_price = stop_level
                    pnl = exit_price - position['entry_price']
                    trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                    'pnl': pnl, 'reason': 'Hard stop', 'date': d})
                    position = None
                    exited = True

                if not exited and exit_mode == 'tp_immediate':
                    if c.High >= position['tp']:
                        exit_price = position['tp']
                        pnl = exit_price - position['entry_price']
                        trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                        'pnl': pnl, 'reason': 'TP floor (immediate)', 'date': d})
                        position = None
                        exited = True

                if not exited and exit_mode == 'next_zone' and confirm_bars == 1:
                    min_zone_level = position['entry_price'] + min_zone_frac * (position['tp'] - position['entry_price'])
                    for z in zones:
                        if z.created_idx <= i and z.level > position['entry_price'] + 1e-9 and z.level >= min_zone_level:
                            if z.touched_by(c, band):
                                weak = (not is_green(c)) if weak_fn == 'not_green' else (not strong_green(c, avg_rng, prev_candle))
                                already_deriskied = ratchet_gate_exit and position['stop'] > position['entry_price'] + 1e-9
                                if weak and not already_deriskied:
                                    exit_price = c.Close
                                    pnl = exit_price - position['entry_price']
                                    trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                                    'pnl': pnl, 'reason': 'Next zone, weak candle', 'date': d})
                                    position = None
                                    exited = True
                                elif ratchet_stop:
                                    # held through this zone on a strong candle -- lock in a rising floor
                                    # just under the cleared zone, instead of only breakeven.
                                    new_stop = z.level - ratchet_buffer
                                    if new_stop > position['stop']:
                                        position['stop'] = new_stop
                                break

                if not exited and exit_mode == 'next_zone' and confirm_bars == 2:
                    min_zone_level = position['entry_price'] + min_zone_frac * (position['tp'] - position['entry_price'])
                    if position.get('pending_weak'):
                        # already flagged weak on a prior candle -- confirm now unless strength resumed
                        if strong_green(c, avg_rng, prev_candle):
                            position['pending_weak'] = False
                        else:
                            exit_price = c.Close
                            pnl = exit_price - position['entry_price']
                            trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                            'pnl': pnl, 'reason': 'Next zone, weak candle (2-bar confirmed)', 'date': d})
                            position = None
                            exited = True
                    if not exited and position is not None:
                        for z in zones:
                            if z.created_idx <= i and z.level > position['entry_price'] + 1e-9 and z.level >= min_zone_level:
                                if z.touched_by(c, band):
                                    if strong_red(c, avg_rng, prev_candle):
                                        exit_price = c.Close
                                        pnl = exit_price - position['entry_price']
                                        trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                                        'pnl': pnl, 'reason': 'Next zone, strong red (instant)', 'date': d})
                                        position = None
                                        exited = True
                                    elif not strong_green(c, avg_rng, prev_candle):
                                        position['pending_weak'] = True
                                    break

                if not exited and exit_mode == 'next_zone' and position is not None:
                    min_zone_level = position['entry_price'] + min_zone_frac * (position['tp'] - position['entry_price'])
                    zones_above = [z for z in zones if z.created_idx <= i and z.level > position['entry_price'] + 1e-9 and z.level >= min_zone_level]
                    if not zones_above and c.High >= position['tp']:
                        exit_price = position['tp']
                        pnl = exit_price - position['entry_price']
                        trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                        'pnl': pnl, 'reason': 'TP floor backstop', 'date': d})
                        position = None
                        exited = True

                if not exited and position is not None and i == n - 1:
                    exit_price = c.Close
                    pnl = exit_price - position['entry_price']
                    trades.append({**position, 'exit_idx': i, 'exit_time': t, 'exit_price': exit_price,
                                    'pnl': pnl, 'reason': 'EOD flatten', 'date': d})
                    position = None
                    exited = True

                if not exited and position is not None:
                    if is_green(c) and c.Close > position['entry_price']:
                        position['stop'] = max(position['stop'], position['entry_price'])

            # ---- look for new entry ----
            if position is None and t != '09:30':
                if '09:35' <= t <= entry_cutoff:
                    established = [z for z in zones if z.created_idx <= i]
                    entry_eligible = [z for z in established if z.kind not in entry_disabled_kinds]
                    touched = [z for z in entry_eligible if z.touched_by(c, band)]
                    if touched:
                        levels_est = [z.level for z in established]
                        hod = rows.iloc[:i+1].High.max()
                        for z in touched:
                            zk = z.key()
                            attempts = zone_attempts.get(zk, 0)
                            if attempts >= max_attempts:
                                continue
                            rank = 'HIGHEST' if z.level == max(levels_est) else ('LOWEST' if z.level == min(levels_est) else 'MEDIUM')
                            if rank in exclude_ranks:
                                continue
                            sg = strong_green(c, avg_rng, prev_candle)
                            wick_ok = long_lower_wick(c, wick_close_frac) and z.kind in ('INTRA_LOW', 'OR_LOW', 'PDL', 'OPEN')
                            # Root-cause fix, scoped narrowly: a wick-confirmed OPEN-zone
                            # entry that still closes BELOW today's open is close to a
                            # contradiction -- price wicked down to the open level and
                            # couldn't even reclaim it. Split by zone kind, this is the one
                            # clearly bad case (OPEN below-open: 44% win rate vs. 80% for
                            # OPEN above-open); PDL and INTRA_LOW below-open bounces are
                            # fine as-is (75% and 62%) and are NOT filtered.
                            if wick_ok and wick_require_above_open and z.kind == 'OPEN' and not (c.Close > rows.iloc[0].Open):
                                wick_ok = False
                            confirmed = sg or wick_ok
                            if not confirmed:
                                continue
                            if rank == 'HIGHEST' and not (c.Close > hod):
                                continue
                            zone_attempts[zk] = attempts + 1
                            is_wide = (day_high_so_far - day_low_so_far) >= wide_day_threshold
                            stop_off = wide_stop if is_wide else normal_stop
                            tp_off = wide_tp if is_wide else normal_tp
                            entry_price = c.Close
                            position = {
                                'entry_idx': i, 'entry_time': t, 'entry_price': entry_price,
                                'stop': entry_price - stop_off, 'tp': entry_price + tp_off,
                                'zone_kind': z.kind, 'zone_level': z.level, 'zone_rank': rank,
                                'attempt': zone_attempts[zk],
                            }
                            break

    return trades

def stats(trades):
    wins = [t for t in trades if t['pnl'] > 0.005]
    losses = [t for t in trades if t['pnl'] < -0.005]
    scratches = [t for t in trades if abs(t['pnl']) <= 0.005]
    n = len(trades)
    net = sum(t['pnl'] for t in trades)
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = -sum(t['pnl'] for t in losses)
    pf = gross_win / gross_loss if gross_loss > 0 else (float('inf') if gross_win > 0 else 0.0)
    wr_excl = len(wins) / max(1, (len(wins) + len(losses))) * 100 if (wins or losses) else 0.0
    return dict(n=n, wins=len(wins), losses=len(losses), scratches=len(scratches),
                win_rate_excl=wr_excl, pf=pf, net=net)

if __name__ == '__main__':
    # Full range currently in the data folder (Jul 1 - Aug 14). Only V1-V7.1
    # are printed by default -- the REJECTED_* presets are for reproducing
    # the negative findings in 06_Lessons_Learned.docx on request, not for
    # routine runs.
    ALL_DAYS = [d for d in days if str(d) >= '2026-07-01']
    WEEKS = [
        ('Week Jul1-2 (partial)', [d for d in ALL_DAYS if str(d) <= '2026-07-02']),
        ('Week Jul6-10',          [d for d in ALL_DAYS if '2026-07-06' <= str(d) <= '2026-07-10']),
        ('Week Jul13-17',         [d for d in ALL_DAYS if '2026-07-13' <= str(d) <= '2026-07-17']),
        ('Week Jul20-24',         [d for d in ALL_DAYS if '2026-07-20' <= str(d) <= '2026-07-24']),
        ('Week Jul27-31',         [d for d in ALL_DAYS if '2026-07-27' <= str(d) <= '2026-07-31']),
        ('Week Aug3-7',           [d for d in ALL_DAYS if '2026-08-03' <= str(d) <= '2026-08-07']),
        ('Week Aug10-14',         [d for d in ALL_DAYS if '2026-08-10' <= str(d) <= '2026-08-14']),
    ]

    print(f"ALL_DAYS: {[str(d) for d in ALL_DAYS]}")
    print()

    for vname in ['V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V7.1']:
        cfg = VERSIONS[vname]
        print(f"\n########## {vname} ##########")
        all_trades = []
        for wname, wdays in WEEKS:
            trades = run_version(cfg, wdays)
            s = stats(trades)
            all_trades.extend(trades)
            print(f"  {wname:22s}  n={s['n']:2d}  W={s['wins']:2d} L={s['losses']:2d} S={s['scratches']:2d}  "
                  f"winrate_excl={s['win_rate_excl']:5.1f}%  PF={s['pf']:5.2f}  net={s['net']:+.3f}")
        s = stats(all_trades)
        print(f"  {'TOTAL (6.4 weeks)':22s}  n={s['n']:2d}  W={s['wins']:2d} L={s['losses']:2d} S={s['scratches']:2d}  "
              f"winrate_excl={s['win_rate_excl']:5.1f}%  PF={s['pf']:5.2f}  net={s['net']:+.3f}")
