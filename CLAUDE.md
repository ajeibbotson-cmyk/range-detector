# Range Detector — Project Context for Claude

This file dumps everything Claude needs to pick up where the previous session left off. The user is iterating on a Pine Script (TradingView) indicator + strategy that detects 1hr structural ranges on US500 for trade entries.

## TL;DR State on Pause (2026-05-06)

- **Symbol/timeframe**: PEPPERSTONE:US500 1hr
- **Current files in this repo**: `indicator.pine` (latest live logic), `strategy.pine` (mirrors indicator + adds entries/exits)
- **TradingView cloud script names**:
  - Indicator: `Impulsive Break & Retracement v1 CC 0505` (title shown as "Range Detector")
  - Strategy: `Range Detector Strategy`
- **What works**: HH/HL/LL/LH classification with confirmation gating; continuation breaks; flip breaks; range-box drawing with active-vs-historical fade; fractal markers locked to actual prices via `location.absolute`.
- **What's still wrong**: Indicator over-fires breaks. Specifically the user said the **April 29 bear break shouldn't fire** — at that bar no structural low actually broke (per their reading). My code's `low <= refL_p` triggers somewhere a wick clipped a level my code thought was structural but the user thinks is internal/noise.
- **Next debugging step**: Add `log.info()` debug output to print `current_HH_p`, `candidate_HL_p`, `refL_p`, etc. on each bar around April 29-30, and trace why the bear flip fires 7h late vs the user's expected 29/4 11:00.

## Strategy Rules (the live model)

This is what we worked out with the user across multiple iterations. **Implement to match this exactly.**

### Bias and structural pivots

The market is in one of three biases: bullish (1), bearish (-1), or neutral (0). Bias starts neutral and gets set on the first qualifying break.

Pivots are classified at each Bill Williams 5-bar fractal:
- **HH** = fractal high > prior fractal high
- **HL** = fractal low > prior fractal low
- **LL** = fractal low < prior fractal low
- **LH** = fractal high < prior fractal high

### Confirmation gating (the key insight)

A pivot is only **structural** after a confirmation event. Internal/noise pivots get ignored.

- **HL becomes structural HL** only when its move breaks above the prior HH (i.e., when price >= `current_HH_p`). The HH break IS the confirmation.
- **LH becomes structural LH** only when its move breaks below the prior LL (price <= `current_LL_p`).

This is the user's verbatim rule: *"the HL @ 0200 breaks the HH (fri 24) impulsively. i then wait for price to come back into that area for an entry. If the fractal indicator marks it as structure inside those points i view it as internal until it breaks as confirmation"*. "Impulsively" doesn't matter for the algorithm — any close above the HH counts. (The user said: *"its a break above the high"* and isn't requiring impulsiveness for now.)

### Bias-gated tracking

User's other principle: *"any black dots i haven't marked is INTERNAL structure, i tend not to trade it as its generally against the trend."* HHs/HLs only matter in bull-or-neutral; LLs/LHs only in bear-or-neutral. Implementation:
- In bull bias: ignore LLs/LHs (they're counter-trend internal noise).
- In bear bias: ignore HHs/HLs.
- In neutral: track both, whichever side breaks first sets bias.

### Break events (each creates a new range box)

User: *"its not just flips. We trade the trend until it fails."* So both **continuation** and **flip** events draw new ranges:

| Event | When | New range | Bias after |
|---|---|---|---|
| HH break (continuation) | bull bias, `high >= current_HH_p` AND have candidate HL | `[candidate_HL, current_HH]` | bull |
| LL break (continuation) | bear bias, `low <= current_LL_p` AND have candidate LH | `[current_LL, candidate_LH]` | bear |
| HH break (initial) | neutral, first HH break | same as continuation | bull |
| LL break (initial) | neutral, first LL break | same as continuation | bear |
| HL break (flip) | bull bias, `low <= refL_p` (the structural HL) | `[refL_p, structural_HH_p]` | bear |
| LH break (flip) | bear bias, `high >= refH_p` | `[structural_LL_p, refH_p]` | bull |

Priority order on a single bar (in case multiple conditions true): continuation first, flip second. After any break fires, skip subsequent break checks for that bar (`newBreak` guard).

### Range mechanics

- **Range** = `[rLo, rHi]` per the events above
- **mid** = `(rHi + rLo) / 2`
- **Entry zone** = `mid ± (mid * zoneWidth%)` where `zoneWidth = 0.15%` default
- **Active range box** extends from break bar to current bar (right edge updates each bar)
- **Historical range boxes** stay drawn but their colors fade to gray when superseded

### Strategy entries (in `strategy.pine`)

On each `newBreak` (continuation or flip), if flat:
- **Long** (bias = 1): entry at limit=`mid`, SL at `rLo`, TP at `mid + (mid - rLo) * rrRatio` (default rrRatio = 3)
- **Short** (bias = -1): entry at limit=`mid`, SL at `rHi`, TP at `mid - (rHi - mid) * rrRatio`

User confirmed: *"The strategy only trades the direction of the 1hr"* — only one direction per range.

User dropped 1m execution: *"lets just trade the 1hr trend, not the 1m"*. Original chart annotations referenced FVG/CISD/Internal-sweep mechanics on 1m for entry refinement — these are NOT being implemented in the current iteration. Strategy is purely 1hr-only.

## Code Architecture

`indicator.pine` and `strategy.pine` share the structural detection logic (lines 1-160 ish). Strategy adds:
- `strategy(...)` declaration in line 2 (with capital, qty, etc.)
- Entry/exit block (after `mid/zHalf/zTop/zBot` calc)
- Entry/SL/TP line drawings in the new-break drawing block

Key state variables (both files):

```pine
var float lastFH_p, lastFL_p          // most recent fractal high/low (any kind)
var float current_HH_p, current_LL_p  // most recent unbroken HH (in bull) / LL (in bear)
var float candidate_HL_p, candidate_LH_p  // pending HL/LH awaiting confirmation
var float refH_p, refL_p              // confirmed structural breakable levels
var float structural_HH_p, structural_LL_p  // the HH/LL that confirmed refL_p/refH_p (used for flip-event range)
var int bias                          // -1 / 0 / 1
var float rHi, rLo                    // current active range
```

Reset behavior on each event type:
- HH break: reset `current_HH`, `candidate_HL`, all bear-side state (`refH_p`, `structural_LL_p`).
- LL break: reset bear cands + bull-side state.
- HL break (flip): reset all bull-side state. Bear-side state to be built fresh from new fractals.
- LH break (flip): reset all bear-side state.

## Iteration history (so you don't repeat mistakes)

We went through these incarnations:
1. **v1**: Plain "any fractal break" → fired on every micro-pullback. Way too noisy.
2. **v2 (strict HL/LH)**: Only update `refL_p` when fractal low > prior fractal low. Same `refH_p` logic for LH. Better but still noisy.
3. **v3 (gates: HH-then-HL)**: Added `needHHforHL` / `needLLforLH` gates so HL only counts after HH. Helped but didn't fix everything.
4. **v4 (reset opposite ref on flip)**: After bear flip, set `refH_p = na` so a stale old LH below current price doesn't immediately trigger bull flip back. **Critical fix.** Eliminated immediate counter-flips.
5. **v5 (confirmation by HH break)**: Replaced gates with explicit `current_HH_p` + `candidate_HL_p` model. HL becomes structural only when current HH actually breaks. This is what's in this repo.
6. **v6 (continuation breaks)**: Each HH break in bull (or LL break in bear) draws a *new* range box, not just flip events. User confirmed this is correct: *"its not just flips. We trade the trend until it fails."* Live in this repo.
7. **v7 (bias-gated tracking)**: Don't track HH/HL when bias is bear, don't track LL/LH when bias is bull. Live in this repo.

## Other things we discovered

### Pine gotchas
- `location.abovebar` / `location.belowbar` use the *current* bar's high/low for Y, NOT the offset bar's. With `offset=-2` on `plotshape`, the shape lands on the right bar (x) but rides current bar's high (y). **Fix**: use `location.absolute` and pass the actual price (`high[2]` or `low[2]`) as the series.
- `display = display.all - display.price_scale` excludes a plot from the price-scale auto-fit calculation. Without this, fractal triangles at very low historical prices (e.g. 6300) compressed all candles into a thin band when zoomed.
- `box.new(left, top, right, bottom)` — note left/right are bar indices, top/bottom are prices.
- `//@version=6` MUST be at column 1 of line 1. A leading space invalidates it and Pine falls back to v3/v4 syntax.
- Pine line continuations need to be indented (>= 1 space). Otherwise the parser treats the broken line as a new statement.
- `pine_smart_compile` (MCP tool) clicks "Pine Save" — saves the script but doesn't auto-add to chart. To add: open script in editor, click "Add to chart" UI button.
- After `pine_set_source`, the on-chart instance auto-refreshes if it's bound to the same script ID. If not, remove + re-add.

### TV chart UX gotcha (took an hour to find)
- If indicator drawings appear "detached" from price action (don't move when chart pans/zooms), the indicator is on the **wrong scale** in TV. Right-click indicator → Pin to Scale → Right (or whichever axis the price uses). Per the user: *"fixed, needed to default to pin to scale"*. Not a script issue.

### MCP tool quirks (TradingView server)
- `mcp__tradingview__chart_set_visible_range` may return a wider `actual` range than `requested` — TV constrains to loaded data.
- `pine_open` opens a script in the editor but if Pine Editor panel isn't open, it errors. Use `ui_open_panel` first.
- `pine_set_source` works when editor is open AND a script is open. If "Could not open Pine Editor" error: re-open panel + script.
- `data_get_pine_labels` caps default at 50 labels visible (out of total). Pass `max_labels` higher to see more.

## Open issues / next steps

1. **April 29 false bear break (HIGHEST PRIORITY)**: User-reported. The indicator fires a bear break around 18:00 but per user's structural reading the actual HL break happens at 11:00 (so my code is 7h late, OR the user's annotation date is off — needs verification). User-provided prices for April 29: HH=7162.7 (04:00), HL=7144.4 (05:00), HH=7163.2 (10:00), break low=7144.2 (11:00). These tight numbers (0.5pt HH spacing, 0.2pt break) match bars near `1777424400` (low 7144.4) and `1777446000` (low 7144.2) in the OHLCV data. User's chart appears to be UTC+4. **Approach**: Add `log.info()` to the indicator that prints state on each bar in this window. Compile, then read `pine_get_console` to trace exactly when/why the break fires.

2. **Possible refinement: 1hr-only filter on fractals**: The user uses Bill Williams 5-bar which captures a lot of internal pivots. Once #1 is debugged, consider whether a longer-period fractal (7-bar or 9-bar) or ZigZag-style minimum-percent filter would better match the user's "external structure" reading.

3. **Strategy validation**: Once indicator's break detection matches user's structural reading, run the strategy in TV strategy tester and check trade win-rate / drawdown. User mentioned target = 3R, BE @ 1.5R (currently strategy only has fixed TP at 3R, no BE move).

4. **Original PRD mechanics not implemented**: The user's chart annotation references additional rules (mitigate 50% / HT FVG / AOI, internal sweep, IFVG 1m, CISD, BE @ 1.5R). The user explicitly said *"lets just trade the 1hr trend, not the 1m"* so these are deferred. Document only — don't build until requested.

## How to resume next session

1. Read this CLAUDE.md.
2. Verify TV connection: `mcp__tradingview__tv_health_check`.
3. Open the latest indicator/strategy in the editor and verify they match this repo's files.
4. Pick up at "Open issues #1" — add `log.info()` instrumentation around the `current_HH_p` / `candidate_HL_p` / break-event blocks. Compile, set chart visible range to April 29 area, read console output, and trace.

## Useful prompts the user has given

- "We trade the trend until it fails." — confirms continuation-breaks-create-ranges model.
- "any black dots i haven't marked is INTERNAL structure" — user differentiates external vs internal pivots.
- "the HL @ 0200 breaks the HH (fri 24) impulsively. i then wait for price to come back into that are for an intry." — describes the confirmation rule.
- "lets just trade the 1hr trend, not the 1m" — defer 1m execution mechanics.
- "I'm looking to trade continuations until it fails." — goal.

## User's Fractals indicator

The user has a custom "Fractals" indicator on chart that draws black dots at fractal highs/lows. They confirmed: *"i currently map things using the fractals indicator that shows in black."* This appears to be Bill Williams 5-bar default — same logic as our `fh`/`fl` formulas. They visually identify which dots are external (HH/HL/LL/LH) vs internal.

## Don't do

- Don't add backwards-compat shims for older code versions.
- Don't add comments explaining what code does — the user reads diffs.
- Don't sneak in "improvements" beyond what's been agreed (e.g. don't add ATR filters, don't add session filters, don't add multi-timeframe logic without checking).
- Don't try to manually paste code into the TV editor for the user — push via `pine_set_source` then `pine_smart_compile`. Pasting via UI has bitten us (whitespace/leading-space issues, see "Pine gotchas").
