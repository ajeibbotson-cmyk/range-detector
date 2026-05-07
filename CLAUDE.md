# Range Detector — Project Context for Claude

This file dumps everything Claude needs to pick up where the previous session left off. The user is iterating on a Pine Script (TradingView) indicator + strategy that detects 1hr structural ranges on US500 for trade entries.

## TL;DR State on Pause (2026-05-07)

- **Symbol/timeframe**: PEPPERSTONE:US500 1hr
- **Current files in this repo**: `indicator.pine` (latest live logic v13), `strategy.pine` (needs update to match indicator), `trace.py` (offline Python trace tool)
- **TradingView cloud script names**:
  - Indicator: `Impulsive Break & Retracement v1 CC 0505` (title shown as "Range Detector")
  - Strategy: `Range Detector Strategy`
- **What works**: HH/HL/LL/LH classification with confirmation gating; continuation breaks; flip breaks; range-box drawing with active-vs-historical fade; fractal markers locked to actual prices via `location.absolute`; configurable `minPivotPct` threshold (now **0.20%**) for HH/LL classification; **counter-flip refs** prevent indicator from getting permanently stuck in one bias. May 4-6 structural sequence verified correct: BER→BUL flip→BUL [7283.4, 7299.1]→BUL [7306.9, 7344.0].
- **What changed this session (v13)**: Two fixes applied together: (1) `minPivotPct` raised from 0.15% to 0.20% — prevents FH at 7239.3 from qualifying as HH (13pts < 14.5pt threshold), eliminating false micro-range cascade and false BER flips in the May 5-6 rally. (2) **flip-lock removed** — `flipHH_lock`/`flipLL_lock` and the seeding of `current_HH_p`/`current_LL_p` from the flip level were removed entirely. After a flip, the indicator now waits for genuine HH/LL fractals to form before firing continuation breaks. This fixed the inverted box problem where rHi < rLo after a flip (e.g., the BUL box at 7283.4 was showing [7248.8, 7283.4] instead of [7283.4, 7299.1]).
- **What needs re-verification**: The April 29 bear continuation area changed because flipLL_lock was also removed. The old `[7144.6, 7162.7]` bear box is no longer present — bear breaks there are now at different levels (7152.1, 7119.5). Needs user review during day-by-day walkthrough.
- **What's still noisy**: Indicator produces 503 breaks across full history — still too many intermediate breaks. Day-by-day walkthrough with the user is still needed to calibrate.
- **Chart rendering note**: With 500 drawing objects spanning 4700-7300+, the Y-axis gets compressed. User may need to re-pin indicator to price scale. Consider reducing drawing limits.
- **Next step**: Re-verify April 29 area with user. Then continue day-by-day walkthrough to reduce noise.

## Strategy Rules (the live model)

This is what we worked out with the user across multiple iterations. **Implement to match this exactly.**

### Bias and structural pivots

The market is in one of three biases: bullish (1), bearish (-1), or neutral (0). Bias starts neutral and gets set on the first qualifying break.

Pivots are classified at each Bill Williams 5-bar fractal:
- **HH** = fractal high > prior fractal high + threshold (`minPivotPct`, default 0.20%)
- **HL** = fractal low that doesn't qualify as LL (i.e., NOT below prior - threshold)
- **LL** = fractal low < prior fractal low - threshold
- **LH** = fractal high that doesn't qualify as HH (i.e., NOT above prior + threshold)

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
| HL break (flip) | bull bias, `close <= refL_p` (the structural HL) | `[refL_p, lastFH_p]` | bear |
| LH break (flip) | bear bias, `close >= refH_p` | `[lastFL_p, refH_p]` | bull |

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
- HL break (flip): set `refH_p := max(rHi, high)` for counter-flip, reset all bull-side state. New fractals build bear-side state from scratch.
- LH break (flip): set `refL_p := min(rLo, low)` for counter-flip, reset all bear-side state. New fractals build bull-side state from scratch.

## Iteration history (so you don't repeat mistakes)

We went through these incarnations:
1. **v1**: Plain "any fractal break" → fired on every micro-pullback. Way too noisy.
2. **v2 (strict HL/LH)**: Only update `refL_p` when fractal low > prior fractal low. Same `refH_p` logic for LH. Better but still noisy.
3. **v3 (gates: HH-then-HL)**: Added `needHHforHL` / `needLLforLH` gates so HL only counts after HH. Helped but didn't fix everything.
4. **v4 (reset opposite ref on flip)**: After bear flip, set `refH_p = na` so a stale old LH below current price doesn't immediately trigger bull flip back. **Critical fix.** Eliminated immediate counter-flips.
5. **v5 (confirmation by HH break)**: Replaced gates with explicit `current_HH_p` + `candidate_HL_p` model. HL becomes structural only when current HH actually breaks. This is what's in this repo.
6. **v6 (continuation breaks)**: Each HH break in bull (or LL break in bear) draws a *new* range box, not just flip events. User confirmed this is correct: *"its not just flips. We trade the trend until it fails."* Live in this repo.
7. **v7 (bias-gated tracking)**: Don't track HH/HL when bias is bear, don't track LL/LH when bias is bull. Live in this repo.
8. **v8 (minPivotPct threshold)**: Added `minPivotPct` input (default 0.15%). Fractal must exceed prior by this % to qualify as HH/LL; below threshold → classified as LH/HL. Filters the 0.5pt HH difference (7162.7→7163.2) that was causing false continuations. Default changed from 0.05% to 0.15% (≈10.7pts at US500 7100) to filter more aggressively.
9. **v9 (flip range uses lastFH_p/lastFL_p)**: Changed flip break range definition. Bear flip `rHi` now uses `lastFH_p` (most recent fractal high) instead of `structural_HH_p`. Bull flip `rLo` uses `lastFL_p` instead of `structural_LL_p`. This gives the range a top/bottom that reflects the most recent failed swing, not an old structural level.
10. **v10 (deepest HL attempt — REVERTED)**: Tried only advancing `refL_p` if new candidate_HL was LOWER than existing refL_p. This caused refL_p to get stuck at ancient levels and prevented flips entirely. Reverted immediately.
11. **v11 (keep deeper refL_p with safety valve — REVERTED)**: On bull continuations, only advance `refL_p` if new `candidate_HL` is lower (deeper), with `maxRangePct` (5%) safety valve forcing advancement when refL_p is too far below current_HH. Same fundamental flaw as v10: refL_p stays at deep levels, bear flip never fires. No bear break in the April 29 area at all. Reverted.
12. **v12 (flip-lock)**: After a flip, seed `current_LL_p`/`current_HH_p` from the flip's break level and protect it with `flipLL_lock`/`flipHH_lock` booleans. Deep impulse LL/HH detections during the locked phase are skipped (don't overwrite current_LL/HH, don't clear candidate_LH/HL). Lock released on first continuation break. Python trace shows bear continuation at `[7144.6, 7162.7]` at Apr 29 07:00 UTC — close to user's expected `[7144.4, 7163.2]` (0.2pt low diff, 0.5pt high diff). Live in this repo.
13. **v12b (counter-flip refs — CRITICAL FIX)**: After deploying v12, discovered the indicator was stuck in bear bias at price level 5555 while US500 was at 7350. Root cause: after an HL flip, `refH_p` was never set, so a LH flip (the only way back to bull) was impossible. Same deadlock existed symmetrically on LH flip. **Fix**: on each flip, set the opposite-side ref (`refH_p := rHi` on HL flip, `refL_p := rLo` on LH flip) so a counter-flip can fire if the thesis fails immediately. This means: if you flip to bear but price reclaims the flip's high, you flip back to bull. With this fix, indicator produces 505 breaks across full history and current range is BULLISH [7306.9, 7344.0] matching today's price of ~7350. Live in this repo.
14. **v13 (threshold 0.20% + flip-lock removed)**: Two fixes applied together to resolve the May 4-6 structural sequence:
    - **Threshold raised to 0.20%**: At 0.15%, FH at 7239.3 was 13pts above lastFH — exceeded the 10.8pt threshold, qualifying as HH. This created a fragile micro-range that cascaded into false BER flips in the May 5-6 rally. At 0.20%, the threshold is 14.5pts, so 13pts doesn't qualify → classified as LH instead → no micro-range → no false BER cascade.
    - **flip-lock removed entirely**: `flipHH_lock`/`flipLL_lock` variables and all associated logic deleted. After a flip, the code no longer seeds `current_HH_p`/`current_LL_p` from the flip level. Instead, it waits for genuine HH/LL fractals to form before the first continuation break can fire. This fixed the inverted box problem: previously, after a bull flip, `current_HH_p` was seeded at the flip level (7248.8) and locked. The first fractal low (7283.4, which was ABOVE 7248.8) triggered a premature HH break with `rHi=7248.8, rLo=7283.4` — an inverted range. With the lock removed, the first real HH fractal (7299.1) sets `current_HH_p`, then the HL fractal (7283.4) sets `candidate_HL_p`, and the break fires correctly with `[7283.4, 7299.1]`.
    - **Verified**: May 4-6 sequence matches user's expected structure. BUL box [7283.4, 7299.1] correct. No false BER labels in rally. BUL [7306.9, 7344.0] correct.
    - **Side effect**: April 29 area changed — old bear continuation `[7144.6, 7162.7]` no longer present. Bear breaks there moved to different levels. Needs re-verification. Live in this repo.

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
- `pine_get_console` appears to NOT read runtime `log.info()` output — returned 0 entries even after adding extensive logging and compiling. May only read compilation output. **Workaround**: use `data_get_ohlcv` to get bar data, then run the algorithm offline in Python (`trace.py`) for bar-by-bar state tracing. This is faster and more reliable than trying to read Pine logs.

## Open issues / next steps

1. **April 29 bear break — NEEDS RE-VERIFICATION**: v13 removed flip-lock, which changed the April 29 area. The old `[7144.6, 7162.7]` bear box is gone — bear breaks there are now at different levels (7152.1, 7119.5). Needs user review during day-by-day walkthrough to confirm these are acceptable.

2. **Too many intermediate breaks**: The indicator produces ~500 breaks across full history — likely too noisy. The counter-flip refs enable rapid flip-flopping in choppy price action. Need user review of broader chart to identify where breaks should NOT fire. The day-by-day walkthrough approach (user's suggestion) is still the right calibration method.

3. **Chart scale/rendering issue**: With 500 boxes/labels/lines spanning the full price range (4700 to 7300+), the chart Y-axis gets compressed. The user may need to re-pin the indicator to the price scale. Consider reducing `max_boxes_count`/`max_labels_count`/`max_lines_count` or adding a lookback limit that deletes drawings older than N bars.

4. **Remove log.info() instrumentation**: The indicator still has `log.info()` calls throughout for debugging. These should be removed once calibration is complete, to keep the code clean and avoid hitting Pine's log limits.

5. **Strategy validation**: Once indicator's break detection is user-approved, update `strategy.pine` to mirror the v13 indicator logic (no flip-lock, 0.20% threshold, counter-flip refs), then run in TV strategy tester.

6. **Possible refinement: fractal filter**: Consider whether a longer-period fractal (7-bar or 9-bar) or ZigZag-style minimum-percent filter would reduce noise. Defer until after day-by-day walkthrough.

7. **Original PRD mechanics not implemented**: The user's chart annotation references additional rules (mitigate 50% / HT FVG / AOI, internal sweep, IFVG 1m, CISD, BE @ 1.5R). The user explicitly said *"lets just trade the 1hr trend, not the 1m"* so these are deferred. Document only — don't build until requested.

## How to resume next session

1. Read this CLAUDE.md.
2. Verify TV connection: `mcp__tradingview__tv_health_check`.
3. Open the latest indicator/strategy in the editor and verify they match this repo's files.
4. Re-verify April 29 area with user — v13 changed bear breaks there (old `[7144.6, 7162.7]` is gone, new levels at 7152.1, 7119.5). User needs to confirm acceptability.
5. Begin day-by-day walkthrough: user marks which fractals are structural vs internal at each step, code gets calibrated to match.
6. Consider reducing drawing limits or adding lookback pruning if chart rendering is problematic.
7. Update `strategy.pine` to match v13 indicator logic once indicator is user-approved.

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
