*Source: extracted from `CNQ_5min_zone_strategy v2.pages` (uploaded 2026-08-19). This charter consolidates the user's working draft with the formalized "ChatGPT version" found later in the same document.*

## Project Name
CNQ 5-Minute Zone Strategy — Research, Validation & Automated Trading System

## Project Objective
Develop a rules-based, long-only trading system for CNQ 5-minute regular-session candles that:

- Converts the current discretionary trading rules (see `02_Core_Trade_Strategy_Rules.md`) into precise, machine-testable rules.
- Tests the strategy against historical CNQ data.
- Identifies which individual rules actually contribute to profitability.
- Improves the strategy without introducing look-ahead bias or overfitting.
- Validates the improved strategy on unseen / out-of-sample data.
- Eventually converts the validated strategy into an automated live-trading system.

## Primary Goal
Develop a strategy with positive expectancy after realistic trading costs, a robust win rate, and acceptable drawdown. The system should **not** be optimized for maximum historical profit or maximum win rate alone. Instead it should optimize across a combination of: net profit, profit factor, expectancy per trade, win rate, maximum drawdown, risk-adjusted return, number of trades, and stability across different market periods and out-of-sample performance.

## Core Philosophy (non-negotiable)
The strategy must behave exactly as a trader would have behaved at that moment in history. At every 5-minute candle close, the system may use only:

- The current candle
- Previously completed candles
- Prior-session information (prior day's high/low/close)
- Zones that had already been established at that point in time
- Information that was objectively available at that time

It must **never** use: future candles, the eventual high/low of the day, future zone formation, or future price action to decide whether a past trade/setup was valid. Future information may only be used later, in the backtest, to calculate the eventual outcome of a trade — never to make the decision itself.

## Project Structure
This project is organized as follows (all docs live in the `CNQ_ H Strategy_Day Trader` folder):

| Doc | Purpose |
|---|---|
| `00_Project_Charter.md` | This document |
| `01_Phases_of_Development.md` | Phase 1 (research) and Phase 2 (live automation), stages and gates |
| `02_Core_Trade_Strategy_Rules.md` | **The trading strategy itself** — zones, entry, confirmation, risk, exit, no-trade rules |
| `03_Data_Folder.md` | Historical data inventory and data-handling / dataset-split plan |
| `04_Test_Protocol.md` | How the strategy is to be backtested — walk-forward methodology, metrics, overfitting controls |
| `05_Full_Test_Report.md` | Template for recording backtest results (to be filled in after each test run) |
| `06_Lessons_Learned.md` | Audit notes from discretionary trading + ongoing research log |

## Note on source conflicts
The uploaded document contains three overlapping passages: (1) the user's informal working draft, (2) a "Prompt for Claude" formalization, and (3) a longer "ChatGPT version" with an explicit charter/phase structure. Where these disagree on a specific number (e.g. the trade-entry window cutoff), the conflict is flagged explicitly in `02_Core_Trade_Strategy_Rules.md` rather than silently resolved, since only the user can confirm which value is authoritative.
