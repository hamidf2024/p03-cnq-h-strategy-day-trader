"""
Stage 9: full 6.3-year historical validation of V1-V7.1.

Runs bt7.py's unchanged, official run_version() logic against the full
2020-07-27 to 2026-11-18 CNQ 5-min history (data/raw/CNQ_5min_20200727_to_20261118.csv)
instead of the narrow Jul1-Aug14 2026 window every version was previously
tuned/reported on. No strategy logic is touched -- this script only changes
which days are fed into the same bt7.run_version()/stats() functions already
used throughout the project.

Validation (required before trusting anything below): this file's own
Jul1-Aug14 2026 slice must reproduce V7.1's official numbers exactly, since
that period is spliced in verbatim from the original Yahoo-sourced CSV
(see data/README.md for why: the rest of the file comes from a different
data vendor -- Alpaca's IEX feed -- and this project's sub-cent zone
thresholds are sensitive enough to vendor differences that an unverified
swap would silently change results).

Usage: put data/raw/CNQ_5min_20200727_to_20261118.csv at ./cnq.csv,
alongside this file and bt7.py, then: python3 stage9_full_history_validation.py
"""
import sys
sys.path.insert(0, '.')
from bt7 import VERSIONS, run_version, stats, days
from collections import defaultdict

# --- mandatory validation gate ---
official_days = [d for d in days if '2026-07-01' <= str(d) <= '2026-08-14']
trades = run_version(VERSIONS['V7.1'], official_days)
s = stats(trades)
expected = dict(n=75, win_rate_excl=72.9, pf=3.81, net=2.690)
ok = (s['n'] == expected['n'] and abs(s['win_rate_excl'] - expected['win_rate_excl']) < 0.1
      and abs(s['pf'] - expected['pf']) < 0.01 and abs(s['net'] - expected['net']) < 0.001)
print(f"Validation gate: n={s['n']} wr={s['win_rate_excl']:.1f}% pf={s['pf']:.2f} net={s['net']:+.3f}  "
      f"(expected n=75 wr=72.9% pf=3.81 net=+2.690)  {'PASS' if ok else 'FAIL -- STOP, do not trust results below'}")
assert ok, "Data file does not reproduce the official Jul1-Aug14 window -- do not proceed."
print()

# --- full-history run, all versions ---
print(f"Full history: {len(days)} trading days, {days[0]} -> {days[-1]}\n")
print(f"{'Ver':6} {'Trades':>7} {'WinRate':>8} {'PF':>6} {'NetTotal':>10} {'Net/Trade':>10}")
all_results = {}
for v in ['V1', 'V2', 'V3', 'V4', 'V5', 'V6', 'V7', 'V7.1']:
    trades = run_version(VERSIONS[v], days)
    s = stats(trades)
    all_results[v] = trades
    print(f"{v:6} {s['n']:7d} {s['win_rate_excl']:7.1f}% {s['pf']:6.2f} {s['net']:10.3f} {s['net']/s['n']:10.4f}")

# --- year-by-year breakdown for the versions discussed in the writeup ---
def stats_for(trade_list):
    wins = [t for t in trade_list if t['pnl'] > 0.005]
    losses = [t for t in trade_list if t['pnl'] < -0.005]
    n = len(trade_list)
    net = sum(t['pnl'] for t in trade_list)
    gross_win = sum(t['pnl'] for t in wins)
    gross_loss = -sum(t['pnl'] for t in losses)
    pf = gross_win / gross_loss if gross_loss > 0 else (float('inf') if gross_win > 0 else 0.0)
    wr = len(wins) / max(1, (len(wins) + len(losses))) * 100 if (wins or losses) else 0.0
    return n, wr, pf, net

for v in ['V1', 'V3', 'V7', 'V7.1']:
    by_year = defaultdict(list)
    for t in all_results[v]:
        by_year[str(t['date'])[:4]].append(t)
    print(f"\n=== {v} by year ===")
    for year in sorted(by_year):
        n, wr, pf, net = stats_for(by_year[year])
        print(f"  {year}: n={n:4d} wr={wr:5.1f}% pf={pf:5.2f} net={net:+8.3f} net/trade={net/n:+.4f}")
