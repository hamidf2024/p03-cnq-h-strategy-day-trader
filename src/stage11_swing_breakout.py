"""
Stage 11: ATR-based Donchian-channel breakout SWING/TREND system for CNQ.

Why this is a genuinely different method, not a parameter tweak on V1-V7.1/
Rule-OR-Model: every prior version is a same-day, EOD-flattened, mean-
reversion "zone bounce" trade on 5-minute bars, with a fixed-DOLLAR stop/
target (0.10/0.20 normal, 0.15/0.30 wide day) -- unchanged in dollar terms
across 2020's ~$9-13 stock and 2026's ~$30-56 stock. Quantitative feasibility
check (done before writing this file, see docs write-up) showed:
  - CNQ's own daily high-low range in 2024-2026 averages only ~2.0-2.4% of
    open -- so an intraday, same-day-exit trade structure cannot average
    >1% net of losers; that would require capturing roughly half of the
    ENTIRE day's range on every single trade, including losers.
  - Multi-day swings are large enough to make >1%/trade plausible: 2024-2026
    rolling 5-day range averages ~5.5-7.0% of open, 10-day ~8.2-10.6%,
    20-day ~12.0-15.5%.
This file tests a classic, well-documented systematic trend-following
design sized to capture a share of THAT multi-day range: the "Turtle
Trading" / Donchian-channel breakout system (Richard Dennis / Richard
Donchian lineage) --
    Entry:  close breaks above the prior N-day high (long) or below the
            prior N-day low (short) -- N tested at 20 and 55 (the two
            classic Turtle System 1 / System 2 windows).
    Stop:   entry +/- 2 x ATR(20) (computed on DAILY bars, 20-day simple
            rolling mean of true range) -- the standard Turtle risk unit.
    Exit:   close crosses the opposite M-day channel (M tested at 10 and
            20) -- a trailing, trend-following exit; OR the 2xATR stop.
            No fixed profit target -- deliberately, since this project's
            own lessons doc found 4 separate "let winners run" variants
            ALL FAILED for the existing same-day mean-reversion zone-bounce
            setup, but explicitly flagged that finding as specific to that
            setup and NOT yet tested on a structurally different
            (trend-following) method -- this is that test.
    Sizing: single unit (no Turtle-style pyramiding) -- kept out of scope
            deliberately, same "narrow grid, state free params up front"
            discipline as Stage 10, to avoid multiplying free parameters.
    Scope:  both long and short (long-only was flagged in the lessons doc
            as "structurally weaker in multi-day downtrends" with no
            mechanical fix found yet for the OLD mean-reversion setup; a
            trend-following short entry is a different mechanism, worth
            testing on its own merits here).

Same walk-forward discipline as Stage 10 (stage10_walk_forward_training.py):
    Train (parameter grid, selected on TRAINING-year trades only):
        fold1: train 2020            -> blind-check 2021
        fold2: train 2020-2021       -> blind-check 2022
        fold3: train 2020-2022       -> blind-check 2023
    Final frozen config: grid re-selected on ALL of 2020-2023, by the same
    rule (best net %/trade on training years, MIN_TRADES floor).
    Blind test: frozen config run once each on 2024, 2025, 2026, and once
    on the three combined -- never touched during selection.

No-look-ahead: the N-day channel and the 20-day ATR used to decide today's
entry/exit are built from bars STRICTLY BEFORE today (shift(1) before any
rolling calculation touches "today").
"""
import json
import numpy as np
import pandas as pd

RAW_CSV = 'data/CNQ_5min_20200727_to_20261118.csv'
MIN_TRADES = 8  # swing trades are much rarer than 5-min zone touches; floor
                 # scaled down from Stage 10's 30 accordingly, stated up front.

# --------------------------------------------------------------------------
# Build daily bars from the 5-minute raw data (no look-ahead: each daily bar
# is a pure aggregation of that day's own intraday bars).
# --------------------------------------------------------------------------
def load_daily():
    df = pd.read_csv(RAW_CSV)
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df['date'] = df['Datetime'].dt.date
    df = df.sort_values('Datetime')
    daily = df.groupby('date').agg(
        Open=('Open', 'first'), High=('High', 'max'),
        Low=('Low', 'min'), Close=('Close', 'last'),
    ).reset_index()
    daily['date'] = pd.to_datetime(daily['date'])
    daily = daily.sort_values('date').reset_index(drop=True)
    daily['year'] = daily['date'].dt.year.astype(str)
    return daily


def add_indicators(daily, atr_n=20):
    d = daily.copy()
    prev_close = d['Close'].shift(1)
    tr = pd.concat([
        d['High'] - d['Low'],
        (d['High'] - prev_close).abs(),
        (d['Low'] - prev_close).abs(),
    ], axis=1).max(axis=1)
    # ATR available for use on day i must only use TR up to day i-1.
    d['atr'] = tr.rolling(atr_n).mean().shift(1)
    return d


def donchian_channels(d, entry_n, exit_n):
    # Channels used to decide action on day i are built from days strictly
    # before i (shift(1)) -- no look-ahead.
    d = d.copy()
    d['entry_hi'] = d['High'].rolling(entry_n).max().shift(1)
    d['entry_lo'] = d['Low'].rolling(entry_n).min().shift(1)
    d['exit_hi'] = d['High'].rolling(exit_n).max().shift(1)
    d['exit_lo'] = d['Low'].rolling(exit_n).min().shift(1)
    return d


# --------------------------------------------------------------------------
# Single-pass simulation over the FULL continuous history for one
# (entry_n, exit_n) config. Trades can span fold/year boundaries (this is a
# multi-day system, unlike bt7's no-cross-day-state property) -- trades are
# bucketed into year-groups by ENTRY date afterward, for walk-forward
# selection/reporting, which introduces no look-ahead since entry_n/exit_n
# are never re-chosen using a trade's own future outcome.
# --------------------------------------------------------------------------
def simulate(d, entry_n, exit_n, allow_short=True):
    trades = []
    position = None  # dict: side, entry_date, entry_price, stop
    n = len(d)
    warmup = max(entry_n, exit_n, 20) + 1
    for i in range(warmup, n):
        row = d.iloc[i]
        date = row['date']
        o, h, l, c = row['Open'], row['High'], row['Low'], row['Close']
        atr = row['atr']
        if pd.isna(atr) or atr <= 0:
            continue

        if position is not None:
            side = position['side']
            exited = False
            if side == 'long':
                if l <= position['stop']:
                    exit_price = position['stop']
                    trades.append(_close(position, date, exit_price, 'Stop (2xATR)'))
                    position = None
                    exited = True
                elif not pd.isna(row['exit_lo']) and c < row['exit_lo']:
                    exit_price = c
                    trades.append(_close(position, date, exit_price, f'{exit_n}-day channel exit'))
                    position = None
                    exited = True
            else:  # short
                if h >= position['stop']:
                    exit_price = position['stop']
                    trades.append(_close(position, date, exit_price, 'Stop (2xATR)'))
                    position = None
                    exited = True
                elif not pd.isna(row['exit_hi']) and c > row['exit_hi']:
                    exit_price = c
                    trades.append(_close(position, date, exit_price, f'{exit_n}-day channel exit'))
                    position = None
                    exited = True

        if position is None:
            if not pd.isna(row['entry_hi']) and c > row['entry_hi']:
                position = dict(side='long', entry_date=date, entry_price=c,
                                 stop=c - 2 * atr, entry_n=entry_n, exit_n=exit_n)
            elif allow_short and not pd.isna(row['entry_lo']) and c < row['entry_lo']:
                position = dict(side='short', entry_date=date, entry_price=c,
                                 stop=c + 2 * atr, entry_n=entry_n, exit_n=exit_n)
    # flatten any still-open position at the final available bar (mirrors
    # bt7's EOD-flatten-at-end-of-data convention, applied at end of history)
    if position is not None:
        last = d.iloc[-1]
        exit_price = last['Close']
        trades.append(_close(position, last['date'], exit_price, 'End-of-data flatten'))
    return trades


def _close(position, exit_date, exit_price, reason):
    side = position['side']
    pnl = (exit_price - position['entry_price']) if side == 'long' else (position['entry_price'] - exit_price)
    return dict(side=side, entry_date=position['entry_date'], entry_price=position['entry_price'],
                exit_date=exit_date, exit_price=exit_price, pnl=pnl, reason=reason,
                entry_n=position['entry_n'], exit_n=position['exit_n'])


def dollar100_stats(trades):
    n = len(trades)
    if n == 0:
        return dict(n=0, gross_pct_avg=0.0, gross_pct_total=0.0, win_rate=0.0, pf=0.0,
                    net_at1c_avg=0.0, avg_hold_days=0.0)
    d100 = [100.0 * (t['pnl'] / t['entry_price']) for t in trades]
    wins = [x for x in d100 if x > 0]
    losses = [x for x in d100 if x < 0]
    gross_win = sum(wins)
    gross_loss = -sum(losses)
    pf = gross_win / gross_loss if gross_loss > 0 else (float('inf') if gross_win > 0 else 0.0)
    wr = len(wins) / max(1, (len(wins) + len(losses))) * 100
    # 1 cent/share round-trip cost on a (100/entry_price)-share position,
    # expressed in the same $100-normalized % terms -- identical convention
    # to Stage 10's dollar100_stats.
    d100_at1c = [100.0 * ((t['pnl'] - 0.01) / t['entry_price']) for t in trades]
    hold_days = [(pd.Timestamp(t['exit_date']) - pd.Timestamp(t['entry_date'])).days for t in trades]
    return dict(n=n, gross_pct_avg=sum(d100) / n, gross_pct_total=sum(d100),
                win_rate=wr, pf=pf, net_at1c_avg=sum(d100_at1c) / n,
                avg_hold_days=sum(hold_days) / n)


GRID = [(20, 10), (20, 20), (55, 10), (55, 20)]
TRAIN_YEARS = ['2020', '2021', '2022', '2023']
TEST_YEARS = ['2024', '2025', '2026']
FOLDS = [
    ('fold1', ['2020'], '2021'),
    ('fold2', ['2020', '2021'], '2022'),
    ('fold3', ['2020', '2021', '2022'], '2023'),
]


def build_grid_trades(d, allow_short=True):
    """One simulate() call per grid candidate over the FULL history, then
    bucket completed trades by ENTRY year. Grid candidates differ only in
    entry_n/exit_n so ATR(20) indicator columns are shared; channel columns
    rebuilt per candidate."""
    out = {}
    for (en, ex) in GRID:
        dd = donchian_channels(d, en, ex)
        trades = simulate(dd, en, ex, allow_short=allow_short)
        out[(en, ex)] = trades
    return out


def trades_in_years(trades, years):
    yrs = set(years)
    return [t for t in trades if str(pd.Timestamp(t['entry_date']).year) in yrs]


def best_by_net_pct_per_trade(grid_trades, years):
    best = None
    for (en, ex), trades in grid_trades.items():
        sub = trades_in_years(trades, years)
        if len(sub) < MIN_TRADES:
            continue
        s = dollar100_stats(sub)
        if best is None or s['gross_pct_avg'] > best[0]:
            best = (s['gross_pct_avg'], en, ex, s, len(sub))
    return best


def walk_forward(label, allow_short):
    d0 = load_daily()
    d0 = add_indicators(d0, atr_n=20)
    grid_trades = build_grid_trades(d0, allow_short=allow_short)

    result = {'label': label, 'folds': {}, 'grid_candidate_counts': {
        f"{en}/{ex}": len(trades) for (en, ex), trades in grid_trades.items()}}

    for name, train_years, val_year in FOLDS:
        picked = best_by_net_pct_per_trade(grid_trades, train_years)
        if picked is None:
            result['folds'][name] = dict(train_years=train_years, val_year=val_year, note='no candidate cleared MIN_TRADES floor on training years')
            continue
        npt, en, ex, s_train, n_train = picked
        val_trades = trades_in_years(grid_trades[(en, ex)], [val_year])
        s_val = dollar100_stats(val_trades)
        result['folds'][name] = dict(train_years=train_years, val_year=val_year,
                                       chosen_entry_n=en, chosen_exit_n=ex,
                                       train=s_train, val=s_val)

    # Final frozen config: same rule over ALL of 2020-2023
    picked = best_by_net_pct_per_trade(grid_trades, TRAIN_YEARS)
    if picked is None:
        result['final'] = {'note': 'no candidate cleared MIN_TRADES floor on 2020-2023'}
        return result
    npt, en, ex, s_train, n_train = picked
    result['final'] = dict(chosen_entry_n=en, chosen_exit_n=ex, train=s_train)

    final_trades = grid_trades[(en, ex)]
    result['test'] = {}
    for y in TEST_YEARS:
        sub = trades_in_years(final_trades, [y])
        result['test'][y] = dollar100_stats(sub)
    combined = trades_in_years(final_trades, TEST_YEARS)
    result['test']['combined'] = dollar100_stats(combined)
    result['_final_trades_combined_detail'] = [
        {k: (str(v) if isinstance(v, pd.Timestamp) else v) for k, v in t.items()}
        for t in combined
    ]
    return result


def main():
    out = {}
    out['long_short'] = walk_forward('Donchian breakout, long+short', allow_short=True)
    out['long_only'] = walk_forward('Donchian breakout, long only', allow_short=False)
    with open('stage11_swing_results.json', 'w') as f:
        json.dump(out, f, indent=2, default=str)
    for label, res in out.items():
        print(f"\n===== {label} =====")
        print(json.dumps({k: v for k, v in res.items() if not k.startswith('_')}, indent=2, default=str))


if __name__ == '__main__':
    main()
