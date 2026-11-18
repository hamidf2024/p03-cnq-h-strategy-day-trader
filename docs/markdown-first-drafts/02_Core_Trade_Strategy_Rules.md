**This is the core trade strategy specification** — the actual rules the backtester and (eventually) the live system must implement. Everything else in this project (phases, test protocol, test report, lessons learned) exists to validate or refine what's written here.

## Market and Window
- Symbol: CNQ
- Timeframe: 5-minute candles
- Regular session only: 09:30–16:00 ET
- Skip the 09:30 candle as an entry candle — it only establishes Zone 1 (the opening price).
- Intraday only. One trade at a time. Flatten by end of session if still in.

> **⚠️ Unresolved conflict — needs your confirmation:** the informal draft says the trade window runs "09:35 through 1:55 ET" (13:55) and separately says "skip the first two bars." The formalized version says the trade-entry window is **09:35–12:55 ET, with no new trade at or after 13:00 ET**. These do not match. Pick one before backtesting — this document does not silently resolve it.

## Zones
A zone is a **price band** (typically 0.05–0.10 wide, wider if price is consolidating there), not a single price.

**Zone 1:** the day's regular-session open.

**Prior-session zones** (known at the open): previous day's high, low, close.

**Intraday zones:** created when price establishes and confirms a swing or horizontal base. Defined generally as a price range that creates resistance — seen when there's a *second* pullback from the top or bottom of that range. The first high/low of the day can become a zone only with second-pullback confirmation. A tight two-pullback range between the day's high and low can also form a medium zone.

**First-low / first-high rule (important):** the first print of a new low is **not** automatically a zone and is **not** an entry. Mark the area, do not enter, wait for the second low/retest — the second low is what establishes the lower zone. The same principle should be tested for intraday highs. The backtester should explicitly tag each candle as `FIRST_LOW`, `SECOND_LOW`, `ZONE_CREATED`, or `ENTRY_ALLOWED` so this rule is auditable.

Do not create zones just because a price is a round number — only draw zones supported by the rules above.

## Entry — Long Only
1. Price must touch an established zone (highest zone, a medium zone, or the lowest zone).
2. Confirmation must occur on that **same candle** — no tag-only entries.

### Confirmation (need at least ONE)
**A. Strong green candle**
- Large body, covering most of the candle range.
- Larger than nearby candles.
- Closes near its high.
- Must be **stronger than the previous red candle** — bigger body and/or bigger total range. If the prior red candle is equal to or bigger, skip the trade. A swing alone is not enough.
- Objective variables to test when formalizing "stronger than previous red": body size, total range, or both together.

**B. Long lower wick**
- Long lower wick that rejects the zone.
- Only valid once the low zone already exists and has formed — never on the first print of a new low.

### Zone-specific entry rules
- **Highest zone of the day:** the strong green candle must close **above and pass** the High of Day (HOD) known at that historical moment. If it doesn't break HOD, no trade. (Do not use the eventual HOD — only what was known then.)
- **Medium zone:** requires the strong-green confirmation compared against the relevant previous red candle.
- **Lowest zone:** requires the strong-green confirmation compared against the relevant previous red candle; never trade the first print of a new low.

**Entry price:** close of the confirmation candle.

## Risk
- **Normal:** Stop = Entry − 0.10. Take-profit floor = Entry + 0.20 (2:1).
- **Large opening dump / wide day** (≈0.50+ of day-so-far range already printed): Stop = Entry − 0.15. Take-profit floor = Entry + 0.30. ("Wide day" threshold of 0.50 is a baseline to test against 0.40/0.60/0.70 alternatives — see `04_Test_Protocol.md`.)
- The take-profit floor is a floor, not an automatic exit — may hold toward the next higher zone if price action stays constructive.

## Stop Management (breakeven rule)
After entry, if a later bar closes higher (green close, trade in profit), move the stop to entry price or slightly above it. Do not leave the original stop in place once price has closed in the trade's favor.

## Exit — in priority order
1. Hard stop (original or moved breakeven stop).
2. Higher zone reached **and** price action is weak/negative (red candle, resistance, stall, shooting-star rejection) → exit; otherwise continue holding.
3. Take-profit floor, if not holding toward the next zone.
4. End of regular session — flatten if still open.

## No-Trade Conditions (do nothing if any apply)
- No established zone touch.
- First print of a new low (zone not yet confirmed).
- Green confirmation is not strong, or not stronger than the relevant previous red candle.
- At the highest zone and the candle did not close above HOD.
- Already in a trade.
- Current time is at/after the entry-window cutoff (see the unresolved conflict above).
- Required information is unavailable or ambiguous — **when uncertain, do not trade.**

## Decision Audit Record (required per candle)
Every historical candle needs an explainable decision record, e.g.:
```
TIME: 10:40
ZONE TOUCHED: YES        ZONE TYPE: LOWER      ZONE ESTABLISHED: NO
FIRST NEW LOW: YES       STRONG GREEN: YES     PREV RED COMPARISON: PASS
HOD RULE: N/A
DECISION: NO TRADE       REASON: FIRST LOW / ZONE NOT ESTABLISHED
```
The system must be able to explain every trade taken **and** every setup rejected.
