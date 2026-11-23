# Project 3 — CNQ 5-Minute Zone Strategy (Day Trader)

> Turn a discretionary, long-only CNQ 5-minute zone strategy into precise, testable rules,
> backtest it without look-ahead bias, find which rules actually create edge, and validate
> it out of sample before any automation.

| | |
|---|---|
| **Status** | Phase 1 (research & validation) — Version 7.1 is the current recommended configuration |
| **Worked on** | 2026-08-19 (one Claude session); exported 2026-10-28 |
| **Data** | CNQ 5-minute regular-session bars, 2026-05-20 → 2026-08-14 |
| **Best result (V7.1, Jul 1 – Aug 14)** | 75 trades · 72.9% win rate · profit factor 3.81 · gross +2.69 $/share (+0.42/week); **+1.19 after 2¢/share costs** |
| **Goals (set 2026-11-23)** | Gross per trade G1 1% · G2 2% · G3 >3%; win rate WR1 50% · WR2 65% · WR3 >75%; months per year in which the average trade is above 1%: S1 8/12 · S2 10/12 · S3 12/12 |
| **Scored on 2024–2026 (22 models, $1,000 per trade)** | Model J (one trade a month, +4% target, no stop) reaches level 1 on all three goals: +2.24% per trade (G2), 88.6% win rate (WR3), 10 / 12 / 9-of-11 months (S1), with cautions about its loss shape and the number of test runs. Model E (pooled peer model) reaches G1 and WR1: +1.41%, 60.5%. See [`docs/12_Stage13_Peer_Fusion_Research.md`](docs/12_Stage13_Peer_Fusion_Research.md) and [`docs/07_Goals_and_Targets.md`](docs/07_Goals_and_Targets.md) |
| **Earlier targets** | Win rate > 60% ✅ · net > 1.0 $/share per week ❌ (best legitimate: 0.42) |
| **Public report** | https://hamidf2024.github.io/ai-trading/project-03.html |

## Project goal (owner's priorities)

Find the trading model that gives:
1. **Maximum net profit** — the highest priority (and it must hold on weeks the rules weren't tuned on);
2. then a **higher win rate**;
3. with a **reasonable number of trades** (about 1–3 per day).

By these priorities the current best is **V7.1** (+2.69 $/share, 72.9% win rate, 75 trades),
followed by V7 (+2.50) and V4 (+1.60).

## Competitive review (2026-10-28)

[`docs/COMPETITIVE_ANALYSIS.md`](docs/COMPETITIVE_ANALYSIS.md) compares this project with LuxAlgo,
TrendSpider, Trade Ideas Holly, the 5-minute ORB "stocks in play" study, support/resistance
research and trading journals. Key findings:

- **The backtester has no trading costs**, so all profit above is gross. At a 2¢/share round-trip
  cost V7.1 nets **+1.19** (1¢: +1.94; break-even ≈ 3.6¢) and only V7.1 and V7 stay profitable —
  see the appendix of the analysis for every version.
- Competitors test across years, many symbols and both directions; we test 6.4 weeks, one stock,
  long only.

Documents updated (previous versions in `results/version-history/20261028T1900/`):
`docs/00_Project_Charter.docx` (owner's priority order + "Competitive Review — Amendments"),
`docs/01_Phases_of_Development.docx` (new **Stage 7** with 9 upgrades, Phase 2 automation path),
`docs/04_Test_Protocol.docx` (net-of-cost reporting, cost sensitivity, variants tried).

## Repository layout

```
.
├── README.md                         ← this file
├── MANIFEST.sha256                   ← SHA-256 of every file
├── project/PROJECT_SETTINGS.json     ← Claude project name and description
├── docs/                             ← the 7 project documents, final versions (.docx)
│   ├── 00_Project_Charter.docx
│   ├── 01_Phases_of_Development.docx
│   ├── 02_Core_Trade_Strategy_Rules.docx   ← the strategy itself (final: V7.1)
│   ├── 03_Data_Folder.docx
│   ├── 04_Test_Protocol.docx
│   ├── 05_Full_Test_Report.docx            ← V1 → V7.1 results, ledgers, week-by-week
│   ├── 06_Lessons_Learned.docx             ← audit notes + research log
│   └── markdown-first-drafts/              ← the first .md drafts of the 7 documents
├── src/                              ← backtesters
│   ├── bt5_version5_backtester.py
│   ├── bt6_version6_backtester.py
│   └── bt7_unified_backtester_v1_to_v71.py ← reproduces every version V1–V7.1
├── data/
│   ├── raw/CNQ_5min_20260520_to_20260814.csv
│   └── screenshots/                  ← your 11 annotated chart screenshots used to align the rules
├── results/version-history/          ← every earlier issue of the strategy, test report and lessons
└── chats/                            ← full session transcript + complete raw log
```

## Where everything came from

| In this repo | Source | Fidelity |
|---|---|---|
| `docs/`, `src/`, `data/raw/`, `results/version-history/` | All 39 files the session delivered (the same file IDs it saved into `~/Documents/AI Project/CNQ_ H Strategy_Day Trader/`), retrieved from Claude | Byte-for-byte |
| `data/screenshots/` | The 11 images you attached in the session, extracted from the session log | Exact image bytes |
| `chats/raw/` | Complete session log (2,882 events), gzip + split into 9 MB parts | Lossless — see `chats/raw/README.md` |
| `chats/*.md` | Readable transcript derived from the raw log | Every message verbatim; tool calls summarized |

Final versions in `docs/` and `src/` are exactly the files last saved to the Mac folder during the
session. Anything edited by hand in that folder after 2026-08-19 is not included.

## Strategy in one paragraph

Long-only, one trade at a time, 09:30–16:00 ET. Zones: the day's open (Zone 1), prior-day
high/low/close, and intraday highs/lows confirmed by a second pullback (never the first print of a
new low). Entry when price touches an established zone **and** the same candle confirms — a strong
green candle that beats the prior red candle, or a long lower wick. Stop −0.10 / floor +0.20
(−0.15 / +0.30 on wide days), stop to breakeven after a green close, and the default exit is
"next zone reached with no more strong signal". Full rules: `docs/02_Core_Trade_Strategy_Rules.docx`.

## Results (full range Jul 1 – Aug 14, 2026)

Ranked by net profit (then win rate):

| Rank | Version | Key change | Net $/share | Win rate | Trades | Profit factor |
|---|---|---|---|---|---|---|
| 1 | **V7.1** | Reject open-zone wick bounces that don't reclaim the open | **2.690** | **72.9%** | **75** | **3.81** |
| 2 | V7 | Tuned parameters (Jul 27 – Aug 14) | 2.495 | 68.4% | 85 | 2.72 |
| 3 | V4 | Max 2 entries per zone per day | 1.595 | 48.8% | 87 | 1.71 |
| 4 | V3 | Opening-range zone added | 1.279 | 45.0% | 107 | 1.42 |
| 5 | V5 | Exit when no more *strong* signal | 1.274 | 59.0% | 88 | 1.55 |
| 6 | V6 | Opening-range zone exit-only | 1.194 | 58.5% | 72 | 1.59 |
| 7 | V1 | Baseline | 0.250 | 33.3% | 72 | 1.10 |
| 8 | V2 | "Next zone + weak action" becomes default exit | 0.199 | 40.9% | 81 | 1.09 |

Win rate excludes scratch (breakeven) trades. Net is in $ per share, before commissions.
**Reproducibility check (2026-10-28):** running `src/bt7_unified_backtester_v1_to_v71.py` on
`data/raw/CNQ_5min_20260520_to_20260814.csv` reproduces V1, V4, V7 and V7.1 exactly as reported above.

## Running the backtester

```bash
cd src
cp bt7_unified_backtester_v1_to_v71.py bt7.py
cp ../data/raw/CNQ_5min_20260520_to_20260814.csv cnq.csv
python3 bt7.py        # prints every version, week by week
```

## Verifying integrity

```bash
shasum -a 256 -c MANIFEST.sha256
```
