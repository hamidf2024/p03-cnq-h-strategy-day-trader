# Competitive Analysis — Project 3 (CNQ 5-Minute Zone Strategy)

Prepared 2026-10-28. Purpose: compare this project with the tools, services and research it
competes with, and identify what to add so the strategy meets the owner's goal:
**(1) maximum net profit, then (2) higher win rate, with (3) a reasonable number of trades.**

Vendor performance figures are the vendors' own claims unless stated otherwise.

## 1. Competitive landscape

| Competitor | Type | What it does | Relevance |
|---|---|---|---|
| **LuxAlgo** (Supply & Demand zone indicators + Vela / Quant AI backtester) | Commercial indicators + AI backtesting | Zone indicators built on supply/demand bases; zones are "consumed" once price trades through. AI agent turns plain-language rules into backtests reporting net profit, profit factor, win rate, long/short split, daily P&L, weekday performance, trade distribution, **Monte Carlo**, prop-firm stress tests. | Closest tool to what this project does by hand: zone rules → code → backtest. Sets the reporting bar (Monte Carlo, weekday/period breakdowns). |
| **TrendSpider** | Commercial platform | Automated support/resistance and trendlines; no-code Strategy Tester with commissions/slippage inputs; **variance testing across timeframes and date ranges**; **group testing across watchlists/sectors**; Strategy Bots with webhooks and broker routing. $82–321/mo. | Tests a strategy across many symbols and periods; we test one stock over ~6 weeks. Shows the Phase 2 automation path (bots → webhooks → broker). |
| **Trade Ideas — Holly AI** | Commercial AI signals | ~70 strategies; suggests only strategies with backtested win rate >60% and ~2:1 reward/risk; ~3–10 intraday trades/day; both long and short. | Uses the same priorities as the owner (profit, win rate, trade count) but across thousands of stocks and both directions. |
| **Zarattini, Barbon & Aziz 2024** — 5-min ORB on Stocks in Play | Published research | 5-min opening-range breakout, long/short, ATR-based stop, 1% risk sizing, flat by close. Top-20 relative-volume stocks: >1,600% (2016–2023), Sharpe 2.81; unfiltered: Sharpe 0.48. Commission modeled at $0.0035/share; slippage not modeled. | Our V3–V7.1 Opening-Range zone is the same idea. Most of the published edge came from a **relative-volume filter**, which we don't use. Their 8-year test period contrasts with our 6.4 weeks. |
| **Chung & Bellotti 2021** — Evidence of support/resistance levels | Published research | On 1-minute data, levels that have bounced more times are more likely to bounce again, and level strength **decays with time**. | Gives a testable basis for scoring zones by prior touches and age. Our rules count touches only for the same-zone cooldown. |
| **Osler 2000** (NY Fed) — *Support for Resistance* | Published research | Published S/R levels had predictive power for intraday reversals in FX. | Long-standing evidence that zone-based reversal entries can carry information. |
| **TradeZella / Edgewonk** | Trading journals with backtesting | Journal discretionary trades, tag setups, replay/backtest, playbooks. | This project started from discretionary trades; a structured journal of live trades is the natural way to keep feeding real-trade alignment reviews. |

## 2. Where we stand vs. competitors

| Capability | This project | Competitors / literature | Gap and impact on profit |
|---|---|---|---|
| **Trading costs** | **None in the backtester** (net is gross, $/share) | TrendSpider/LuxAlgo include commissions & slippage; ORB paper models commission | **Critical.** V7.1 earns +2.69 $/share gross on 75 trades; at 1¢/share round-trip cost → +1.94, at 2¢ → +1.19, break-even at ~3.6¢. At 2¢ only V7.1 and V7 stay profitable (V4 −0.15, V3 −0.86). |
| Data history | 6.4 weeks backtested (CNQ May–Aug 2026 data) | ORB: 8 years; TrendSpider variance testing | Too short to trust profit; add multi-year CNQ 5-min data |
| Symbols | CNQ only | TrendSpider group tester; Holly/ORB scan thousands | Test a basket of similar liquid energy stocks |
| Direction | Long only | Holly and ORB trade both sides | Short-side mirror could add profit on down days |
| Trade selection | Zone touch + confirmation | ORB: relative-volume ("in play") filter drives most of the edge | Test a relative-volume filter on entries |
| Zone strength | Touch cap of 2 per zone/day | Chung & Bellotti: prior bounces ↑ strength, age ↓ strength | Score zones by bounces and age |
| Robustness stats | Week-by-week table; manual curve-fit checks | LuxAlgo Monte Carlo; TrendSpider variance tests; DSR/PBO | Add Monte Carlo and Deflated Sharpe on version selection |
| Position sizing | Fixed 1 share (P&L in $/share) | ORB: 1% account risk per trade | Report $ equity curve with risk-based sizing |
| Automation | Phase 2 plan, broker unnamed | TrendSpider bots + webhooks + broker routing; Holly auto-trading | Name the alert/broker path for paper trading |
| Reporting | Tables in .docx | Equity curve, drawdown, period returns, trade distribution | Add standard charts (now on the website) |

## 3. Phase 1 roadmap additions (Stage 7, added 2026-10-28)

Added to `docs/01_Phases_of_Development.docx` as **Stage 7 — Competitive-review upgrades**, in
priority order for the profit-first goal:

1. **7.1 Trading costs in the backtester**: commission + spread/slippage per share; re-rank all versions on net profit after costs. *(Highest priority — can change which version is best.)*
2. **7.2 More history**: at least 1–2 years of CNQ 5-minute data; walk-forward by month.
3. **7.3 Basket test**: run V7.1 unchanged on similar liquid stocks (e.g. SU, CVE, IMO, XOM, CVX).
4. **7.4 Relative-volume filter**: test trading only when the day's early volume is above normal.
5. **7.5 Zone strength score**: prior bounce count and zone age as entry filters.
6. **7.6 Short-side mirror**: same rules inverted for resistance zones.
7. **7.7 Monte Carlo + Deflated Sharpe**: resample trade order for drawdown risk; correct version selection for the number of variants tried.
8. **7.8 Risk-based sizing**: e.g. 1% account risk per trade; report a $ equity curve.
9. **7.9 Live journal**: log live discretionary trades in a structured journal to keep calibrating rules.

Phase 2 now names the automation path: alerts/webhooks → broker API paper trading → reconciliation.

## Sources

- LuxAlgo Supply and Demand Zones — https://www.luxalgo.com/library/indicator/VDv1AnDA-supply-and-demand-zones/ ; LuxAlgo backtesting — https://luxalgo.com/backtesting
- TrendSpider review (Day Trading Toolkit, updated 2026-09-24) — https://daytradingtoolkit.com/reviews/trendspider-review
- Trade Ideas review (Liberated Stock Trader) — https://www.liberatedstocktrader.com/trade-ideas-review/
- Zarattini, Barbon & Aziz (2024) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284 ; Tradoki analysis — https://blog.tradoki.com/posts/opening-range-breakout-stocks-in-play-research ; QuantConnect reproduction — https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/
- Chung & Bellotti, Evidence and Behaviour of Support and Resistance Levels in Financial Time Series (2021) — https://arxiv.org/html/2101.07410v1
- Osler, Support for Resistance: Technical Analysis and Intraday Exchange Rates (FRBNY Economic Policy Review, 2000) — https://ideas.repec.org/a/fip/fednep/y2000ijulp53-68nv.6no.2.html
- TradeZella vs Edgewonk — https://www.tradezella.com/vs/edgewonk
- Bailey & López de Prado, The Deflated Sharpe Ratio (2014) — https://papers.ssrn.com/abstract=2460551

## Appendix — cost sensitivity (computed 2026-10-28 with `src/bt7_unified_backtester_v1_to_v71.py`)

Full range Jul 1 – Aug 14, 2026. Net $/share after a round-trip cost per share:

| Version | Trades | Gross | 1¢ cost | 2¢ cost | Win rate |
|---|---|---|---|---|---|
| V7.1 | 75 | 2.690 | 1.940 | 1.190 | 72.9% |
| V7 | 85 | 2.495 | 1.645 | 0.795 | 68.4% |
| V4 | 87 | 1.595 | 0.725 | −0.145 | 48.8% |
| V6 | 72 | 1.194 | 0.474 | −0.246 | 58.5% |
| V5 | 88 | 1.274 | 0.394 | −0.486 | 59.0% |
| V3 | 107 | 1.279 | 0.209 | −0.861 | 45.0% |
| V1 | 72 | 0.250 | −0.470 | −1.190 | 33.3% |
| V2 | 81 | 0.199 | −0.611 | −1.421 | 40.9% |

V7.1 maximum drawdown (gross, $/share, trade sequence): −0.34.
