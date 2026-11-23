# data/

**Price data is not in this repository.** By the owner's decision (2026-11-23)
every price file is kept only in the owner's local project folder: the data
vendor (Alpaca) states that its API data may not be redistributed, and the
owner wants one copy of the data, in one place. `.gitignore` keeps
`data/raw/*.csv` and `data/raw/peers/` out of git. The code, documents and
result summaries in this repository are complete; to re-run them, the price
files have to be present locally under the names below.

## What lives in the local `data/raw/` (not published)

| File | What it is | Source |
|---|---|---|
| `raw/CNQ_5min_20200727_to_20261118.csv` | CNQ 5-minute bars, 2020-07-27 to 2026-11-18 (US/Eastern), 117,169 bars, 1,584 trading days. **The file every result through Stage 12 was computed on.** Alpaca IEX feed, spliced with the original Yahoo file for 2026-05-20 to 2026-08-14 so the published V1-V7.1 results reproduce exactly (V7.1 Jul 1-Aug 14: n=75, 72.9%, PF 3.81, net +2.690). Split-adjusted for CNQ's 2-for-1 on 2024-06-11. | Alpaca (IEX feed) + Yahoo |
| `raw/CNQ_5min_2026-05-20_to_2026-08-14_original_yahoo.csv` | The original 3-month CNQ file the project started from. Its bars are also contained in the file above. | Yahoo |
| `raw/peers/<SYMBOL>_5min_sip_20200727_to_20261123.csv` | 5-minute bars for CNQ, SU, CVE, IMO, XOM, CVX, USO, XLE: consolidated (SIP) feed, split-adjusted, US/Eastern, 09:30-15:55, 1,591 trading days each. The last day (2026-11-23) is partial. On 2021-04-19, 2021-10-25 and 2022-03-08 the files for CNQ, SU, CVE, XOM and CVX hold a single bar: the vendor has no data for those sessions, so treat them as missing. | Alpaca (SIP feed), downloaded 2026-11-23 with `src/stage13_download_peer_oil_data.py` |
| `raw/peers/WTI_spot_daily_EIA.csv`, `..._full_1986_onward.csv`, `RWTCd.xls` | Daily WTI spot price at Cushing, OK. | U.S. Energy Information Administration, series RWTC (public domain) |

How the sources were chosen, their limits and licence terms:
`docs/11_Peer_and_Oil_Data_Sources.md`. Data-quality checks:
`src/stage13_check_peer_data.py`, summary in
`results/experiments/stage13_data_checks.json` (no prices).

## Notes that still apply to the CNQ IEX file

- **Data-vendor sensitivity.** The IEX feed is a small part of the market
  (about 4% of CNQ's volume by this project's own comparison). Against the
  consolidated feed its daily closes differ by 0.02% at the median and by up
  to 1.7%, and it has fewer than 70 of 78 bars on 237 of 1,584 days. The
  intraday zone rules use sub-cent thresholds, so trade-by-trade results on
  this file are directionally reliable but not reproducible bar-for-bar from
  another feed (see `06_Lessons_Learned.docx`, Stage 9).
- **To obtain a CNQ file from scratch** run the download script with a free
  Alpaca account. It produces the consolidated-feed file, not the IEX file
  above, so intraday results will differ slightly from the published ones
  until they are re-run on it.

## In this repository

- `screenshots/` — the 11 annotated chart screenshots shared on 2026-08-19, in
  the order sent. Files 01-05 (17:51 UTC) and 06-11 (18:40 UTC) are the two
  batches used for the "Real-Trade Alignment Review" sections of
  `docs/02_Core_Trade_Strategy_Rules.docx`.
