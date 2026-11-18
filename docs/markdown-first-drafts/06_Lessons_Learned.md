## Purpose
This doc has two parts: (1) the discretionary trading notes captured before this project was formalized — useful for sanity-checking the backtester's logic against real judgment calls — and (2) the ongoing research log for every rule change made during Phase 1 (per `04_Test_Protocol.md`, every modification must be logged here with a hypothesis, result, and accept/reject decision).

## Part 1 — Discretionary Audit Notes (source: user's working draft, dates as written in the original doc)

- **Jul 1:** Walk-forward long was correct.
- **Jul 2:** After a green close in profit, move stop to entry. A triangle into a zone takes the first strong green. The later PDH breakout was the wrong second trade.
- **Jul 6:** First long was correct. The 13:05 trade was wrong (weak green, after 1pm).
- **Jul 7–9:** Results accepted (tiny breakeven scratches from the moved stop).
- **Jul 10:** Walk-forward was correct. No change.
- **Jul 13:** Missed the 10:00–11:00 lower base zone. Intended long at that lower price, close at the higher zone.
- **Jul 14:** First long was wrong — the bounce green was not stronger than the previous red bar.
- **Jul 15:** Do not buy the first touch of the lower price (10:40) even with a strong green. Let the zone form, then trade the later strong signal (11:30–12:00).
- **Jul 16:** Same pattern — the first valid trade was 11:00–11:30, on the second low, after the zone existed, with a strong green vs. the previous red, at the lower price. Do not buy the first low.
- **Jul 17:** Skip the first trade. At the highest zone, the green confirmation must close and pass the High of Day.

**Recurring theme across these notes:** the single most common error was entering on the *first* touch of a new low/high before the zone was actually confirmed by a second test. This is why the first-low/first-high rule in `02_Core_Trade_Strategy_Rules.md` is called out as needing special, explicit handling (and explicit `FIRST_LOW` / `SECOND_LOW` / `ZONE_CREATED` tagging) in the backtester — it's not a minor detail, it's the main recurring mistake in the source material.

## Part 2 — Research Log (append one entry per rule-change test, per Stage 5 of `01_Phases_of_Development.md`)

### Entry template
```
Date:
Hypothesis:
Rule changed:
Reason for change:
Dataset used:
Results summary:
Comparison with baseline:
Statistical impact:
Decision: Accepted / Rejected
Notes:
```

*(No entries yet — first entry gets added once Stage 4's baseline test runs and Stage 5 experiments begin.)*
