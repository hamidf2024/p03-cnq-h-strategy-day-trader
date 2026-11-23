# Free and reliable data for peers and oil (SU, CVE, IMO, XOM, CVX, WTI)

*Added 2026-11-23, at the owner's direction ("through deep research find free
and reliable data for peer and oil data (SU, CVE, IMO, XOM, CVX, WTI)"). This
is the data prerequisite identified at the end of Stage 12
(`10_Stage12_Field_Fusion_Research.md`, next steps 3 and 4). Vendor facts
below were read from the vendors' own pages on 2026-11-23 unless marked
"secondary"; plan limits change, so re-check before relying on them.*

## 0. Recommendation

| Need | Source | Cost | What you get | Why this one |
|---|---|---|---|---|
| **5-minute bars for SU, CVE, IMO, XOM, CVX** (and CNQ re-pulled the same way) | **Alpaca Market Data API, free "Basic" plan** | $0 | History since 2016, any `[1-59]Min` timeframe, 10,000 rows per request, 200 requests/minute, split adjustment on request | The only free source found that covers 5-minute bars back to July 2020. Same vendor as the existing CNQ file. |
| **Intraday oil, time-stamped to the minute** | **USO** (United States Oil Fund) 5-minute bars from the same Alpaca request; optionally **XLE** for the sector | $0 | An exchange-traded proxy for near-month WTI futures, on the same clock and from the same feed as the stocks | No free source of intraday WTI *futures* covering 2020-2026 was found. USO is tradable, liquid and known at decision time. |
| **WTI itself, daily** | **EIA** "Cushing, OK WTI Spot Price FOB" (series RWTC) | $0 | Daily spot price from 1986, public domain | The official series; everyone else's free daily WTI is a copy of it. |

Two findings change how the data should be pulled:

1. **Use the consolidated feed (SIP), not IEX.** Alpaca's free plan allows
   historical requests on the SIP feed (100% of market volume) as long as the
   request's end time is at least 15 minutes old. The IEX feed, which the
   current CNQ file uses, is about 2.5% of market volume. CNQ should be
   re-pulled on SIP together with the peers so that all symbols come from one
   feed, and the Stage 9-12 numbers re-checked against it.
2. **Take WTI from EIA directly, not through FRED.** FRED carries the same EIA
   series (DCOILWTICO), but FRED's terms of use prohibit using its content "in
   connection with the development or training of any software program or
   system or machine learning". EIA's own data is U.S.-government public
   domain.

One licence point was put to the owner (Section 5): Alpaca says its API data
may not be redistributed, and this public repository contained an
Alpaca-sourced CNQ file. The owner decided on 2026-11-23 to keep all price
data in the local project folder only, and that file has been removed from
the repository.

## 1. What is needed

Stage 12 ended with one model worth confirming (the Field-Fusion GBM) and a
sample too small to confirm it. Peer and oil data are meant to supply about
six times the training labels, a blind test on symbols the model has never
seen, and enough trades to tell a real edge from luck. That requires:

- 5-minute regular-session bars, 2020-07-27 to date, for SU, CVE, IMO, XOM,
  CVX -- the same span and layout as
  `data/raw/CNQ_5min_20200727_to_20261118.csv`. All five trade in U.S.
  dollars on U.S. exchanges (IMO on NYSE American, the others on NYSE).
- An oil price known at the decision time (one 5-minute bar before the close),
  so it can be a feature without look-ahead.
- Split-adjusted prices, not dividend-adjusted, to match the CNQ file.

## 2. Stock data: sources compared

| Source | Free 5-minute history | Free limits | Verdict |
|---|---|---|---|
| **Alpaca** (Basic plan) [1][2][3][4] | Since 2016 | 200 requests/min; IEX any time, SIP when the end time is 15+ minutes old; adjustment `raw` / `split` / `dividend` / `all` | **Use this.** |
| EODHD [5] | 5-minute from October 2020 (misses Jul-Sep 2020); not split-adjusted | Free plan is 20 calls/day with 1 year of end-of-day only (secondary [6]); intraday needs the $29.99/month plan | Paid, and starts three months late |
| Massive (formerly Polygon.io) [7][8] | None: free plan is end-of-day, 2 years | 5 calls/min | Cannot reach 2020; even the $29/month plan goes back only 5 years |
| Alpha Vantage [9][10] | None: `TIME_SERIES_INTRADAY` is a premium endpoint | 25 requests/day free; premium from $49.99/month | Paid |
| Tiingo [11][12] | IEX-only intraday; depth not stated | 50 requests/hour, 1,000/day, 500 symbols/month; "internal use only" | Possible backup, but IEX-only like the current file |
| Twelve Data [13] | Depth on the free plan not stated; 1-minute "from Feb 2020" appears only on a paid plan (secondary [6]) | 8 credits/min, 800/day | Unconfirmed; not relied on |
| Finnhub (secondary [6]) | No U.S. intraday candles on the free plan | 60 calls/min | No |
| Financial Modeling Prep (secondary [6]) | End-of-day only on the free plan | 250 calls/day | No |
| Yahoo Finance / yfinance [14] | Last 60 days only for 5-minute; hourly 730 days | Unpublished limits; unofficial; has broken several times | Daily cross-check only |
| Stooq [15] | About the last month of 5-minute bars | Manual download behind a CAPTCHA | Daily cross-check only |
| Schwab Trader API (unofficial docs [16]) | About nine months of 5-minute bars | Needs a Schwab account | Too shallow |

**Request budget.** 1,584 trading days x 78 bars is about 124,000 regular-
session bars per symbol, or 13 requests of 10,000 rows (about 31 if
pre-market and after-hours bars are returned too). Eight symbols is 100-250
requests -- a couple of minutes at the free rate limit.

**Reliability.** Alpaca is a U.S. broker-dealer distributing exchange data;
on the SIP feed the bars are built from all U.S. exchanges. Its limits are
its free plan's conditions, not data quality: the 15-minute rule only matters
for live use, not for history. As with the CNQ file, the pull should pass a
"reproduces a known result" gate before anything is built on it (Section 4).

## 3. Oil data: sources compared

| Source | What it is | Free coverage | Verdict |
|---|---|---|---|
| **EIA, series RWTC** [17][18] | Daily WTI spot at Cushing, dollars per barrel | 1986 to date; free API (registration) or spreadsheet download; public domain, acknowledgment requested | **Use for daily WTI.** |
| FRED, DCOILWTICO [19][20] | The same EIA series | 1986-01-02 to 2026-11-17 at the time of checking | Same numbers, but FRED's terms exclude machine-learning use; use EIA instead |
| EIA NYMEX futures (contracts 1-4) [21] | Daily futures settlements | **Stops at 2024-04-05** ("Futures prices after April 5, 2024, are not available") | Cannot cover the test period |
| **USO via Alpaca** [1][22] | ETF designed to track daily moves of the near-month NYMEX light sweet crude contract | 5-minute bars since 2016, same feed and clock as the stocks | **Use for intraday oil.** A proxy, not WTI itself: it carries roll and fee drag over long horizons, so use its returns, not its level |
| Databento, CME Globex CL [23] | True WTI futures, 1-minute and finer (resolutions and 2010 start are from a secondary source [24]) | $125 of free credit for new users, expiring after 6 months; priced per gigabyte, price for this pull not confirmed | Best upgrade if true intraday futures are wanted; free only within the credit |
| Dukascopy "US Crude Oil" CFD [25][26] | A broker's own quote for light crude, tick data | Free export; earliest data listed as 1983 by a third-party tool | Free intraday oil, but one broker's CFD quote rather than exchange prices; a fallback |
| FirstRate Data [27] | Continuous CL futures, 1-minute to daily, from 2008 | Free sample only; full set is paid | Paid |
| Yahoo `CL=F`, Stooq (secondary [24]) | Daily continuous futures | Free, unofficial, roll method unclear | Daily cross-check only |

**Timing caution for the daily spot series.** EIA publishes the spot price
after the day ends. In a backtest a day's spot price must not be used in that
day's decision; use values up to the previous day at most. USO's 5-minute bars
do not have this problem, which is the main reason to carry both.

## 4. How to pull and check it

`src/stage13_download_peer_oil_data.py` does the download. It needs a free
Alpaca account's API key pair and, for the spot series, a free EIA key, both
supplied through environment variables. It requests `timeframe=5Min`,
`feed=sip`, `adjustment=split`, pages through results, converts to U.S.
Eastern time, keeps the 09:30-15:55 session and writes one CSV per symbol in
the CNQ file's layout to `data/raw/peers/`. Its paging, time-zone and session
logic pass a self-test on mocked responses, and it was run successfully by
the owner on 2026-11-23 (Section 7). Neither host is reachable from the cloud
research environment, so it has to be run on the owner's machine.

To get the data into the project, either of these works:

- run the script on the Mac and leave the files in the project folder; or
- allow `data.alpaca.markets` and `api.eia.gov` for the research environment
  (Settings > Capabilities on claude.ai) and supply the keys for the session.

Checks to run before any model sees the new files (the project's standing
"reproduce a known-good result first" rule):

1. **CNQ, SIP against the existing IEX file:** daily closes should agree
   closely; quantify the difference in the 5-minute bars. Then re-run the
   Stage 12 `verify` logic on the SIP file to see how feed-sensitive the
   daily-bar models are (the intraday zone rules are known to be sensitive).
2. **Splits:** CNQ's 2-for-1 on 2024-06-11 must show no price jump. No split
   is known to this project for SU, CVE, IMO, XOM or CVX in this window, but
   that is not verified: confirm there is no unexplained overnight jump.
3. **Independent daily cross-check:** daily closes built from the 5-minute
   bars against a second free source (Yahoo or Stooq) for each symbol.
4. **Completeness:** trading-day count per symbol equals CNQ's; bars per day
   near 78; no duplicated timestamps.
5. **USO against EIA spot:** daily USO returns should track daily WTI spot
   returns closely; large gaps flag bad data in one of them.

## 5. Licence points for the owner

- **Alpaca:** its support page states "you cannot redistribute Alpaca API
  data" [28]. The page does not define redistribution for an individual's
  non-commercial research repository, and the full terms were not read here.
  The cautious reading is that Alpaca-sourced price files should not sit in a
  public repository. **Decided 2026-11-23:** code, documents and result
  summaries stay public; price files are kept only in the owner's local
  project folder, and `data/raw/CNQ_5min_20200727_to_20261118.csv` was
  removed from the repository's current version (earlier commits still
  contain it; removing it from history would need the repository's history
  to be rewritten, which has not been done).
- **EIA:** public domain; an acknowledgment such as "Source: U.S. Energy
  Information Administration" is requested [17].
- **FRED:** free for personal, non-commercial use, but not for developing or
  training software or machine-learning systems [20] -- so not used here.
- **Tiingo, Twelve Data, Yahoo:** internal or personal use only.

## 6. What was not established

- Alpaca's pages confirm history "since 2016", minute timeframes and the SIP
  rule, but only a live request will confirm that every one of the six
  tickers returns complete 5-minute SIP history back to July 2020.
- Databento's price for six years of 1-minute CL bars (its pricing page could
  not be read here).
- Whether Dukascopy's free export includes the individual stocks; its oil CFD
  is confirmed, the stocks are not.
- Free-plan intraday depth at Twelve Data and Tiingo.

## 7. Collection status (2026-11-23): complete

All of the data in Section 0 has been collected. By the owner's instruction
**every data file is saved only in the owner's local project folder**
(`data/raw/` and `data/raw/peers/`); none of it is in this repository, the
older CNQ price file has been removed from it, and duplicate copies elsewhere
have been deleted. `.gitignore` keeps the price files out of git. What each
local file is: `data/README.md`.

| Item | Result |
|---|---|
| 5-minute bars, consolidated feed, split-adjusted: CNQ, SU, CVE, IMO, XOM, CVX, USO, XLE | **Collected** from Alpaca's free plan. 1,591 trading days each (2020-07-27 to 2026-11-23, the last day partial), about 123,400 regular-session bars per symbol. It took 52 to 86 requests per symbol, more than the estimate in Section 2, because pre-market and after-hours bars come back too and are filtered out. |
| EIA daily WTI spot (series RWTC) | **Collected.** 1,596 days from 2020-07-01 to 2026-11-17 (full history from 1986 also kept). The latest value, 89.53 on 2026-11-17, matches FRED's copy of the series. |
| Independent daily cross-check from a second vendor | **Not done.** No second source was reachable. The feed comparison below is the cross-check in hand. |

Checks (`src/stage13_check_peer_data.py`; summary without prices in
`results/experiments/stage13_data_checks.json`):

| Check | Finding |
|---|---|
| Not empty, well formed | Every file has about 123,400 rows and 7 to 8 MB. No empty cells, no zero or negative prices, no zero-volume bars, no duplicate timestamps, no bars outside 09:30-15:55, no impossible high/low/close rows. The largest single 5-minute move in any symbol is 6.6%. |
| Completeness | All eight symbols have the same 1,591-day calendar and a median of 78 of 78 bars per day. Short days are the scheduled half-days and the partial last day (2026-11-23, 11 bars). **Three real gaps:** on 2021-04-19, 2021-10-25 and 2022-03-08 the five NYSE-listed symbols (CNQ, SU, CVE, XOM, CVX) have a single 09:30 bar and nothing else, while IMO, USO and XLE are complete. The vendor's history is missing those sessions for that group of stocks; the older IEX file lacks the same three days. They are 3 of 1,591 days (0.2%) and must be treated as missing, not as one-bar days. |
| Splits | No overnight move above 20% in any symbol. CNQ's 2-for-1 on 2024-06-11 is adjusted correctly (closes of 35.46 and 35.57 either side). The largest overnight moves are real market days (2020-11-09 for most symbols). |
| Consolidated feed vs the existing IEX file (CNQ) | Daily closes differ by 0.02% at the median, by more than 0.25% on 10 of 1,584 days, and by 1.73% at most (2024-12-23). Daily returns correlate 0.9988. The IEX file is about 4% of the consolidated volume, lacks four days entirely and has fewer than 70 bars on 237 days. Good enough to trust the daily-bar results so far; the intraday zone results should be re-run on the consolidated file before being relied on. |
| Peers against CNQ | Daily-return correlation with CNQ: CVE 0.84, SU 0.83, XLE 0.82, IMO 0.80, XOM 0.74, CVX 0.73, USO 0.64. The Canadian producers are the closest peers, as expected. |
| Oil | Daily WTI spot returns correlate 0.59 with CNQ (0.59 to 0.66 in every year) and 0.91 with USO (0.85 to 0.96 by year). On 10 days spot and USO differ by more than 5 points; the largest are days where the spot series moved without the fund (for example 2026-09-28: spot +15.3%, USO +1.1%), which is a property of the spot series, not bad USO data. This supports using USO for anything time-stamped and the spot series only as daily context. |

How to handle the three gap days: drop them for the five affected symbols
when daily bars are built (a one-bar day would otherwise produce a false daily
range and close), and do not open or close a simulated trade on them.

What this does not cover: a comparison against a second vendor, and whether the
Stage 12 models give the same signals on the consolidated-feed CNQ file. The
second is the first task of Stage 13.

## Sources

1. Alpaca, *About Market Data API* (plans, history, limits) -- https://docs.alpaca.markets/us/docs/about-market-data-api
2. Alpaca, *Market Data FAQ* (SIP history rule for free users) -- https://docs.alpaca.markets/us/docs/market-data-faq
3. Alpaca, *Historical Stock Data* (feeds: IEX ~2.5% of volume, SIP 100%) -- https://docs.alpaca.markets/us/docs/historical-stock-data-1
4. Alpaca, *Historical bars* API reference -- https://docs.alpaca.markets/reference/stockbars
5. EODHD, *Intraday Historical Data API* -- https://eodhd.com/financial-apis/intraday-historical-data-api
6. MarketParquet, *Market Data API Pricing Compared* (secondary) -- https://marketparquet.com/guides/market-data-api-pricing
7. Massive, *Massive vs Alpaca* (vendor-written) -- https://massive.com/compare/massive-vs-alpaca
8. AlgoData Index, *Massive (formerly Polygon)* (secondary) -- https://algodataindex.com/vendors/massive/
9. Alpha Vantage, *API documentation* -- https://www.alphavantage.co/documentation/
10. Alpha Vantage, *Premium* -- https://www.alphavantage.co/premium/
11. Tiingo, *IEX documentation* -- https://www.tiingo.com/documentation/iex
12. Tiingo, *Pricing* -- https://www.tiingo.com/about/pricing
13. Twelve Data, *Pricing* -- https://twelvedata.com/pricing
14. Massive, *Massive vs yfinance* (vendor-written; yfinance limits) -- https://massive.com/compare/massive-vs-yfinance
15. QuantStart, *An Introduction to Stooq Pricing Data* -- https://www.quantstart.com/articles/an-introduction-to-stooq-pricing-data
16. schwab-py, *HTTP Client* (unofficial; price-history depth) -- https://schwab-py.readthedocs.io/en/latest/client.html
17. EIA, *Copyrights and Reuse* -- https://www.eia.gov/about/copyrights_reuse.php
18. EIA, *Cushing, OK WTI Spot Price FOB* -- https://www.eia.gov/dnav/pet/hist/RWTCD.htm ; open data API -- https://www.eia.gov/opendata/
19. FRED, *DCOILWTICO* -- https://fred.stlouisfed.org/series/DCOILWTICO
20. FRED, *Legal notices and terms of use* -- https://fred.stlouisfed.org/legal/
21. EIA, *NYMEX Futures Prices* -- https://www.eia.gov/dnav/pet/pet_pri_fut_s1_d.htm
22. USCF, *United States Oil Fund (USO)* -- https://www.uscfinvestments.com/uso
23. Databento, *Usage pricing and data credits* -- https://databento.com/docs/faqs/usage-pricing-and-data-credits ; energy futures -- https://databento.com/futures/commodity/energy
24. QuantVPS, *CME Historical Data: Free and Cheap Futures Sources* (secondary) -- https://www.quantvps.com/blog/cme-historical-data-complete-guide
25. Dukascopy, *Range of markets* -- https://www.dukascopy.com/swiss/english/cfd/range-of-markets/
26. dukascopy-node (third-party tool; instrument start dates) -- https://github.com/leo4815162342/dukascopy-node
27. FirstRate Data, *Crude Oil WTI Futures (CL)* -- https://firstratedata.com/i/futures/CL
28. Alpaca Support, *Can I redistribute Alpaca API data?* -- https://alpaca.markets/support/redistribute-alpaca-api

*Research and education only, not investment or legal advice.*
