# Range Detector

TradingView Pine Script indicator + strategy that detects 1hr structural ranges on US500 (and other instruments) for trade entries.

## What it does

Tracks bullish/bearish bias by classifying each Bill Williams fractal as HH / HL / LL / LH, then draws a range box on each **structural break event**:

- **Continuation break** — HH break in bull bias (or LL break in bear) defines a fresh range with `[just-confirmed HL, broken HH]` as `[bottom, top]`. Trade in same direction.
- **Flip break** — HL break in bull bias (price drops below the structural HL) flips to bear with the same range. Trade reverses.

The active range box has a 50% mid-line. The strategy version places limit entries at the mid with SL at the opposite range edge and TP at 3R.

## Files

- `indicator.pine` — the visual indicator (no orders)
- `strategy.pine` — same detection logic + `strategy.entry`/`exit` calls
- `CLAUDE.md` — full project context, rules, and history (read this if you're picking up where the last session left off)

## Status

Work in progress. The structural detection logic is mostly correct but still over-fires on some bars where the user wouldn't call a break structurally. See `CLAUDE.md` "Open issues" for next steps.
