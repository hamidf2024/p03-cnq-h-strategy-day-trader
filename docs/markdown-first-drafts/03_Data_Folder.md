## Current Dataset On Hand
Uploaded alongside the strategy document: `CNQ_5min_20260520_to_20260814.csv`

- **Symbol:** CNQ
- **Bar size:** 5-minute
- **Coverage:** 2026-05-20 through 2026-08-14 (60 trading days, 4,680 bars)
- **Columns:** `Datetime` (ET, with UTC offset), `Open`, `High`, `Low`, `Close`, `Volume`, `Dividends`, `Stock Splits`
- **Format:** clean OHLCV, no gaps spot-checked in the header/footer rows; `Dividends`/`Stock Splits` are 0.0 throughout the sample (as expected for 5-min bars).

A copy of this raw CSV is placed alongside these docs in this folder's `data/raw/` subfolder. Treat this doc as the **inventory and handling plan**, not a substitute for looking at the data itself.

## Recommended Data Folder Layout (for the backtesting codebase)
When Stage 2 (historical data engine) is built, organize data on disk as:

```
data/
├── raw/            # untouched vendor exports, e.g. CNQ_5min_20260520_to_20260814.csv
├── clean/          # session-filtered, gap-checked, regular-session-only bars
├── sessions/        # one file per trading day, with prior-day H/L/C precomputed
├── splits/
│   ├── development/    # used to formalize + tune rules (Stage 1, 4, 5)
│   ├── validation/     # used to choose among reasonable rule variations
│   └── out_of_sample/  # held out entirely until Stage 6 — never touched during development
└── walk_forward/    # rolling train/test fold definitions (see 04_Test_Protocol.md)
```

## Data Sufficiency Note
The current dataset spans ~3 months (60 trading days). That's enough to formalize rules and run an initial baseline + a handful of walk-forward folds, but it's thin for a robust out-of-sample validation across different market regimes. Before Phase 2 gates are attempted, plan to extend the historical range (ideally 12+ months covering varied volatility regimes) so the out-of-sample split in `04_Test_Protocol.md` isn't just a few weeks of data.

## Data Quality Checklist (before Stage 2 build)
- Confirm no missing 5-minute bars within regular session hours (09:30–16:00 ET) on any trading day.
- Confirm timestamps are consistently ET with correct DST offset (the sample shows `-04:00`, correct for EDT in this date range).
- Confirm volume values are sane (no zero-volume bars during active session hours, spot-checked).
- Decide how partial/holiday-shortened sessions are handled (excluded vs. included with session-length flag).
