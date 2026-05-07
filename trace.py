#!/usr/bin/env python3
"""
Range Detector Pine Script Algorithm Trace — v12 "flip-lock"
=============================================================
Faithful bar-by-bar replication of the Pine Script Range Detector indicator.
Traces fractal detection, classification, and break events.

v12 changes:
  - flipLL_lock / flipHH_lock state variables
  - FL→LL detection: if flipLL_lock, skip current_LL_p update + candidate_LH_p clear
  - FH→HH detection: if flipHH_lock, skip current_HH_p update + candidate_HL_p clear
  - HL flip (bull→bear): seed current_LL_p from rLo, set flipLL_lock=True, flipHH_lock=False
  - LH flip (bear→bull): seed current_HH_p from rHi, set flipHH_lock=True, flipLL_lock=False
  - LL break: flipLL_lock=False
  - HH break: flipHH_lock=False

Focus window: timestamps 1777240800 to 1777600000
"""

from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# OHLCV data: (timestamp, open, high, low, close)
# ---------------------------------------------------------------------------
bars = [
    (1776988800, 7124.7, 7132.3, 7121.7, 7127.4),
    (1776992400, 7127.7, 7128.7, 7121.9, 7127.7),
    (1776996000, 7127.4, 7127.9, 7111.4, 7113.6),
    (1776999600, 7113.5, 7115.6, 7107.4, 7110.2),
    (1777003200, 7109.9, 7116.2, 7108.2, 7115.4),
    (1777006800, 7115.7, 7122.4, 7110.9, 7121.9),
    (1777010400, 7122.2, 7123.4, 7116.2, 7118.5),
    (1777014000, 7118.3, 7126.5, 7117.5, 7124.7),
    (1777017600, 7124.2, 7130.3, 7112.6, 7114.6),
    (1777021200, 7114.8, 7117.7, 7106.5, 7115),
    (1777024800, 7114.7, 7123.5, 7112.7, 7122),
    (1777028400, 7121.7, 7160.5, 7121.7, 7142),
    (1777032000, 7142.2, 7148.5, 7125.7, 7133.5),
    (1777035600, 7134, 7141.5, 7116.5, 7125.6),
    (1777039200, 7124.2, 7142.5, 7117.7, 7141),
    (1777042800, 7141.6, 7167.9, 7138.7, 7164.7),
    (1777046400, 7165, 7166.7, 7155.5, 7162.7),
    (1777050000, 7163, 7171.5, 7154, 7163.2),
    (1777053600, 7163.5, 7164.7, 7156.2, 7162),
    (1777057200, 7162.5, 7171.2, 7161, 7165.7),
    (1777060800, 7165.9, 7167.9, 7161.2, 7167.4),
    # Weekend gap
    (1777240800, 7157.4, 7164, 7144.6, 7155.4),
    (1777244400, 7155.5, 7155.9, 7148.4, 7151.9),
    (1777248000, 7152.1, 7166.1, 7150.6, 7163.6),
    (1777251600, 7164.1, 7181.1, 7163.1, 7180.8),
    (1777255200, 7180.6, 7181.5, 7175.5, 7176.6),
    (1777258800, 7176.4, 7179.6, 7174.9, 7176.1),
    (1777262400, 7175.9, 7178.4, 7173.1, 7173.9),
    (1777266000, 7173.8, 7174.1, 7161.4, 7162.9),
    (1777269600, 7163.1, 7164.9, 7159.4, 7161.4),
    (1777273200, 7160.9, 7163.4, 7158.4, 7160.3),
    (1777276800, 7160.2, 7163.2, 7154.7, 7162.2),
    (1777280400, 7162.3, 7164.4, 7160.6, 7162.2),
    (1777284000, 7162.4, 7168.4, 7159.9, 7167.2),
    (1777287600, 7167.4, 7171.7, 7166.9, 7169.9),
    (1777291200, 7170.2, 7170.7, 7158.7, 7161.7),
    (1777294800, 7162.2, 7171.7, 7154.2, 7168.7),
    (1777298400, 7168.9, 7172.2, 7158.7, 7164.2),
    (1777302000, 7164.7, 7165.7, 7150.4, 7161.9),
    (1777305600, 7162.2, 7171.1, 7159.7, 7169.4),
    (1777309200, 7169.7, 7180.2, 7167.1, 7176.9),
    (1777312800, 7176.7, 7180.7, 7175.2, 7176.4),
    (1777316400, 7176.2, 7183.9, 7174.9, 7180.1),
    (1777320000, 7180.9, 7180.9, 7175.4, 7178.6),
    (1777327200, 7180.6, 7194.6, 7180.1, 7190.5),
    (1777330800, 7190.4, 7193.9, 7188.9, 7191.1),
    (1777334400, 7191.6, 7197, 7186.1, 7187.6),
    (1777338000, 7187.9, 7193.1, 7182.1, 7182.6),
    (1777341600, 7182.8, 7185.9, 7178.6, 7179.9),
    (1777345200, 7179.6, 7185.9, 7178.8, 7182.2),
    (1777348800, 7182.4, 7186.9, 7181.1, 7183.4),
    (1777352400, 7183.5, 7184.1, 7170.4, 7172.4),
    (1777356000, 7172.3, 7174.9, 7165.2, 7167.8),
    (1777359600, 7167.6, 7171.9, 7164.7, 7170.9),
    (1777363200, 7171.2, 7175.8, 7162.6, 7174.7),
    (1777366800, 7174.4, 7174.9, 7162, 7165.7),
    (1777370400, 7165.9, 7168.5, 7160.2, 7163.2),
    (1777374000, 7164.7, 7165.7, 7129.4, 7132.5),
    (1777377600, 7133.2, 7143.9, 7121.7, 7143.4),
    (1777381200, 7143.3, 7156.9, 7134.7, 7143.7),
    (1777384800, 7143.1, 7151.2, 7120.4, 7133.2),
    (1777388400, 7133.4, 7138.7, 7121.7, 7127.7),
    (1777392000, 7127.9, 7133.7, 7121.4, 7129.4),
    (1777395600, 7129.7, 7139.4, 7122.2, 7138.4),
    (1777399200, 7138.7, 7144.3, 7135.7, 7143.2),
    (1777402800, 7143.4, 7150.2, 7140.4, 7145.6),
    (1777406400, 7145.4, 7150.1, 7141.6, 7146.4),
    (1777413600, 7148, 7152.4, 7148, 7150.7),
    (1777417200, 7150.9, 7154.3, 7149.2, 7154.2),
    (1777420800, 7154.4, 7162.7, 7154.4, 7158.2),
    (1777424400, 7158.3, 7158.3, 7144.4, 7153.2),
    (1777428000, 7153.4, 7159.9, 7153.3, 7156.4),
    (1777431600, 7156.7, 7160.2, 7156.2, 7157.4),
    (1777435200, 7157.7, 7161.7, 7157.4, 7159.4),
    (1777438800, 7159.5, 7161.9, 7156.9, 7159.9),
    (1777442400, 7159.7, 7163.2, 7154.2, 7154.4),
    (1777446000, 7154.6, 7158.2, 7144.2, 7149.4),
    (1777449600, 7150.6, 7154.8, 7141.4, 7147.4),
    (1777453200, 7147.7, 7152.7, 7142.2, 7144.2),
    (1777456800, 7143.9, 7155.7, 7141.4, 7151.2),
    (1777460400, 7151.4, 7154.7, 7144.7, 7148.2),
    (1777464000, 7147.9, 7149.4, 7135.9, 7143.7),
    (1777467600, 7144.2, 7148.2, 7124.7, 7135.7),
    (1777471200, 7136.2, 7150.2, 7130.7, 7142.7),
    (1777474800, 7142.9, 7143.4, 7120.2, 7128.4),
    (1777478400, 7128.7, 7135.6, 7116.9, 7124.9),
    (1777482000, 7125.2, 7135.4, 7119.9, 7133.9),
    (1777485600, 7134.1, 7134.7, 7112.4, 7133.8),
    (1777489200, 7134.2, 7144.9, 7127.9, 7144.9),
    (1777492800, 7145.2, 7165, 7106.3, 7117),
    (1777500000, 7126.5, 7171.7, 7124.2, 7159.7),
    (1777503600, 7159.9, 7168.4, 7155.4, 7167.9),
    (1777507200, 7168.2, 7176.2, 7166.2, 7174.4),
    (1777510800, 7174.2, 7175.9, 7169.2, 7174.7),
    (1777514400, 7174.5, 7175, 7140.9, 7152.5),
    (1777518000, 7152.3, 7156.7, 7146.9, 7147.2),
    (1777521600, 7147.4, 7147.4, 7120.2, 7120.4),
    (1777525200, 7120.7, 7133.9, 7118.5, 7118.7),
    (1777528800, 7118.4, 7133.2, 7109.2, 7128.5),
    (1777532400, 7128.7, 7141.2, 7125, 7136.2),
    (1777536000, 7136.8, 7146.2, 7134.7, 7140.2),
    (1777539600, 7140.5, 7159.6, 7133.8, 7146.4),
    (1777543200, 7146.5, 7161.7, 7146.5, 7156.1),
    (1777546800, 7155.7, 7175.2, 7155.2, 7169.7),
    (1777550400, 7169.6, 7186.5, 7168.5, 7179.5),
    (1777554000, 7179.2, 7185, 7135.7, 7140.6),
    (1777557600, 7141, 7170, 7132.7, 7167.5),
    (1777561200, 7167.6, 7179.5, 7163.2, 7174.7),
    (1777564800, 7175, 7182.5, 7168, 7172.5),
    (1777568400, 7172.3, 7200.7, 7172.2, 7200),
    (1777572000, 7199.7, 7217.2, 7199.7, 7212.7),
    (1777575600, 7212.5, 7226.7, 7211.7, 7213.4),
    (1777579200, 7213.5, 7227.8, 7213.5, 7222.4),
]


def ts_to_utc(ts: int) -> str:
    """Convert Unix timestamp to human-readable UTC string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def main() -> None:
    # Focus window boundaries
    FOCUS_START = 1777240800
    FOCUS_END = 1777600000

    # Parameters
    MIN_PIVOT_PCT = 0.15

    # -----------------------------------------------------------------------
    # State variables (all start as None, matching Pine Script 'na')
    # -----------------------------------------------------------------------
    lastFH_p = None
    lastFL_p = None
    current_HH_p = None
    current_HH_b = None
    current_LL_p = None
    current_LL_b = None
    candidate_HL_p = None
    candidate_HL_b = None
    candidate_LH_p = None
    candidate_LH_b = None
    refH_p = None
    refH_b = None
    refL_p = None
    refL_b = None
    structural_HH_p = None
    structural_HH_b = None
    structural_LL_p = None
    structural_LL_b = None
    bias = 0  # 0=neutral, 1=bull, -1=bear

    # Range output
    rHi = None
    rLo = None

    # v12: flip-lock state
    flipLL_lock = False
    flipHH_lock = False

    # Collect break events for summary
    break_summary = []

    n = len(bars)

    def bias_str(b: int) -> str:
        return {0: "NEUTRAL", 1: "BULL", -1: "BEAR"}[b]

    def in_focus(ts: int) -> bool:
        return FOCUS_START <= ts <= FOCUS_END

    # Print state snapshot helper
    def print_state(label: str = ""):
        if label:
            print(f"  [{label}]")
        print(f"    bias={bias_str(bias)}  lastFH_p={lastFH_p}  lastFL_p={lastFL_p}")
        print(f"    current_HH_p={current_HH_p}  current_LL_p={current_LL_p}")
        print(f"    candidate_HL_p={candidate_HL_p}  candidate_LH_p={candidate_LH_p}")
        print(f"    refH_p={refH_p}  refL_p={refL_p}")
        print(f"    structural_HH_p={structural_HH_p}  structural_LL_p={structural_LL_p}")
        print(f"    flipLL_lock={flipLL_lock}  flipHH_lock={flipHH_lock}")
        if rHi is not None or rLo is not None:
            print(f"    range=[{rLo}, {rHi}]")

    # -----------------------------------------------------------------------
    # Main loop: process bar-by-bar
    # -----------------------------------------------------------------------
    for i in range(n):
        ts_i = bars[i][0]
        high_i = bars[i][2]
        low_i = bars[i][3]

        verbose = in_focus(ts_i)

        # We need at least 5 bars to check fractals (indices [i-4]...[i])
        fh = False
        fl = False

        if i >= 4:
            h0 = bars[i][2]      # high[0]
            h1 = bars[i-1][2]    # high[1]
            h2 = bars[i-2][2]    # high[2]
            h3 = bars[i-3][2]    # high[3]
            h4 = bars[i-4][2]    # high[4]

            l0 = bars[i][3]      # low[0]
            l1 = bars[i-1][3]    # low[1]
            l2 = bars[i-2][3]    # low[2]
            l3 = bars[i-3][3]    # low[3]
            l4 = bars[i-4][3]    # low[4]

            fh = (h4 < h2) and (h3 <= h2) and (h2 >= h1) and (h2 > h0)
            fl = (l4 > l2) and (l3 >= l2) and (l2 <= l1) and (l2 < l0)

        # -------------------------------------------------------------------
        # Fractal classification
        # -------------------------------------------------------------------
        if fh:
            fractal_price = bars[i-2][2]
            fractal_ts = bars[i-2][0]
            fractal_bar = i - 2

            threshH = (lastFH_p if lastFH_p is not None else 0) * MIN_PIVOT_PCT / 100
            isHH = (lastFH_p is not None) and (fractal_price > lastFH_p + threshH)
            isLH = (lastFH_p is not None) and (not isHH)

            if verbose:
                print(f"\n{'='*80}")
                print(f"BAR {i}: {ts_to_utc(ts_i)}  (ts={ts_i})")
                print(f"  OHLC: O={bars[i][1]} H={high_i} L={low_i} C={bars[i][4]}")
                print(f"  FRACTAL HIGH detected at bar {fractal_bar} ({ts_to_utc(fractal_ts)})")
                print(f"    fractal price = {fractal_price}")
                print(f"    lastFH_p = {lastFH_p}")
                print(f"    threshH = {threshH:.4f}")
                if lastFH_p is not None:
                    print(f"    fractal_price > lastFH_p + threshH? {fractal_price} > {lastFH_p + threshH:.4f} => {isHH}")
                    if isHH:
                        print(f"    => Classified as HH")
                    else:
                        print(f"    => Classified as LH")
                else:
                    print(f"    => FIRST fractal high (no prior FH to compare)")

            hh_applied = False
            lh_applied = False

            if isHH and bias != -1:
                # v12: check flipHH_lock
                if flipHH_lock:
                    if verbose:
                        print(f"    HH LOCKED (flipHH_lock=True) — skipping current_HH_p update and candidate_HL_p clear")
                        print(f"      lastFH_p updated: {lastFH_p} -> {fractal_price}")
                else:
                    current_HH_p = fractal_price
                    current_HH_b = fractal_bar
                    candidate_HL_p = None
                    candidate_HL_b = None
                    hh_applied = True
                    if verbose:
                        print(f"    HH APPLIED (bias={bias_str(bias)} != BEAR)")
                        print(f"      current_HH_p = {current_HH_p}")
                        print(f"      candidate_HL cleared")
            elif isHH and bias == -1:
                if verbose:
                    print(f"    HH IGNORED (bias=BEAR, gate: bias != -1 failed)")

            if isLH and bias != 1:
                candidate_LH_p = fractal_price
                candidate_LH_b = fractal_bar
                lh_applied = True
                if verbose:
                    print(f"    LH APPLIED (bias={bias_str(bias)} != BULL)")
                    print(f"      candidate_LH_p = {candidate_LH_p}")
            elif isLH and bias == 1:
                if verbose:
                    print(f"    LH IGNORED (bias=BULL, gate: bias != 1 failed)")

            lastFH_p = fractal_price

            if verbose and not isHH and not isLH:
                print(f"    (No classification - first FH)")

        if fl:
            fractal_price = bars[i-2][3]
            fractal_ts = bars[i-2][0]
            fractal_bar = i - 2

            threshL = (lastFL_p if lastFL_p is not None else 0) * MIN_PIVOT_PCT / 100
            isLL = (lastFL_p is not None) and (fractal_price < lastFL_p - threshL)
            isHL = (lastFL_p is not None) and (not isLL)

            if verbose:
                if not fh:
                    print(f"\n{'='*80}")
                    print(f"BAR {i}: {ts_to_utc(ts_i)}  (ts={ts_i})")
                    print(f"  OHLC: O={bars[i][1]} H={high_i} L={low_i} C={bars[i][4]}")
                print(f"  FRACTAL LOW detected at bar {fractal_bar} ({ts_to_utc(fractal_ts)})")
                print(f"    fractal price = {fractal_price}")
                print(f"    lastFL_p = {lastFL_p}")
                print(f"    threshL = {threshL:.4f}")
                if lastFL_p is not None:
                    print(f"    fractal_price < lastFL_p - threshL? {fractal_price} < {lastFL_p - threshL:.4f} => {isLL}")
                    if isLL:
                        print(f"    => Classified as LL")
                    else:
                        print(f"    => Classified as HL")
                else:
                    print(f"    => FIRST fractal low (no prior FL to compare)")

            ll_applied = False
            hl_applied = False

            if isLL and bias != 1:
                # v12: check flipLL_lock
                if flipLL_lock:
                    if verbose:
                        print(f"    LL LOCKED (flipLL_lock=True) — skipping current_LL_p update and candidate_LH_p clear")
                        print(f"      lastFL_p updated: {lastFL_p} -> {fractal_price}")
                else:
                    current_LL_p = fractal_price
                    current_LL_b = fractal_bar
                    candidate_LH_p = None
                    candidate_LH_b = None
                    ll_applied = True
                    if verbose:
                        print(f"    LL APPLIED (bias={bias_str(bias)} != BULL)")
                        print(f"      current_LL_p = {current_LL_p}")
                        print(f"      candidate_LH cleared")
            elif isLL and bias == 1:
                if verbose:
                    print(f"    LL IGNORED (bias=BULL, gate: bias != 1 failed)")

            if isHL and bias != -1:
                candidate_HL_p = fractal_price
                candidate_HL_b = fractal_bar
                hl_applied = True
                if verbose:
                    print(f"    HL APPLIED (bias={bias_str(bias)} != BEAR)")
                    print(f"      candidate_HL_p = {candidate_HL_p}")
            elif isHL and bias == -1:
                if verbose:
                    print(f"    HL IGNORED (bias=BEAR, gate: bias != -1 failed)")

            lastFL_p = fractal_price

            if verbose and not isLL and not isHL:
                print(f"    (No classification - first FL)")

        # -------------------------------------------------------------------
        # Break events (check in order, only one per bar)
        # -------------------------------------------------------------------
        newBreak = False
        break_type = None

        # HH break (bull continuation or initial)
        if ((bias == 1 or bias == 0)
                and current_HH_p is not None
                and high_i >= current_HH_p
                and candidate_HL_p is not None):
            old_bias = bias
            bias = 1
            refL_p = candidate_HL_p
            refL_b = candidate_HL_b
            structural_HH_p = current_HH_p
            structural_HH_b = current_HH_b
            rHi = current_HH_p
            rLo = candidate_HL_p
            newBreak = True
            break_type = "HH BREAK"
            current_HH_p_old = current_HH_p
            candidate_HL_p_old = candidate_HL_p
            current_HH_p = None
            current_HH_b = None
            candidate_HL_p = None
            candidate_HL_b = None
            refH_p = None
            refH_b = None
            structural_LL_p = None
            structural_LL_b = None
            # v12: unlock flipHH_lock on HH break
            flipHH_lock = False

            if verbose or in_focus(ts_i):
                print(f"\n  >>> HH BREAK at bar {i} ({ts_to_utc(ts_i)})")
                print(f"      high={high_i} >= current_HH_p={current_HH_p_old}")
                print(f"      candidate_HL_p={candidate_HL_p_old}")
                print(f"      bias: {bias_str(old_bias)} -> BULL")
                print(f"      range = [{rLo}, {rHi}]")
                print(f"      refL_p = {refL_p}")
                print(f"      flipHH_lock = False (unlocked by HH break)")
                print_state("Post HH BREAK state")

            if in_focus(ts_i):
                break_summary.append({
                    "bar": i,
                    "ts": ts_i,
                    "type": "HH BREAK",
                    "high": high_i,
                    "low": low_i,
                    "rHi": rHi,
                    "rLo": rLo,
                    "old_bias": bias_str(old_bias),
                    "new_bias": "BULL",
                    "refL_p": refL_p,
                    "refH_p": refH_p,
                })

        # LL break (bear continuation or initial)
        if (not newBreak
                and (bias == -1 or bias == 0)
                and current_LL_p is not None
                and low_i <= current_LL_p
                and candidate_LH_p is not None):
            old_bias = bias
            bias = -1
            refH_p = candidate_LH_p
            refH_b = candidate_LH_b
            structural_LL_p = current_LL_p
            structural_LL_b = current_LL_b
            rHi = candidate_LH_p
            rLo = current_LL_p
            newBreak = True
            break_type = "LL BREAK"
            current_LL_p_old = current_LL_p
            candidate_LH_p_old = candidate_LH_p
            current_LL_p = None
            current_LL_b = None
            candidate_LH_p = None
            candidate_LH_b = None
            refL_p = None
            refL_b = None
            structural_HH_p = None
            structural_HH_b = None
            # v12: unlock flipLL_lock on LL break
            flipLL_lock = False

            if verbose or in_focus(ts_i):
                print(f"\n  >>> LL BREAK at bar {i} ({ts_to_utc(ts_i)})")
                print(f"      low={low_i} <= current_LL_p={current_LL_p_old}")
                print(f"      candidate_LH_p={candidate_LH_p_old}")
                print(f"      bias: {bias_str(old_bias)} -> BEAR")
                print(f"      range = [{rLo}, {rHi}]")
                print(f"      refH_p = {refH_p}")
                print(f"      flipLL_lock = False (unlocked by LL break)")
                print_state("Post LL BREAK state")

            if in_focus(ts_i):
                break_summary.append({
                    "bar": i,
                    "ts": ts_i,
                    "type": "LL BREAK",
                    "high": high_i,
                    "low": low_i,
                    "rHi": rHi,
                    "rLo": rLo,
                    "old_bias": bias_str(old_bias),
                    "new_bias": "BEAR",
                    "refL_p": refL_p,
                    "refH_p": refH_p,
                })

        # HL break (flip bull to bear)
        if (not newBreak
                and bias == 1
                and refL_p is not None
                and low_i <= refL_p):
            old_bias = bias
            bias = -1
            rLo = refL_p
            rHi = lastFH_p if lastFH_p is not None else high_i
            newBreak = True
            break_type = "HL FLIP"
            refL_p_old = refL_p
            refL_p = None
            refL_b = None
            structural_HH_p = None
            structural_HH_b = None
            current_HH_p = None
            current_HH_b = None
            candidate_HL_p = None
            candidate_HL_b = None
            # v12: seed current_LL from rLo, set flipLL_lock, clear flipHH_lock
            current_LL_p = rLo
            current_LL_b = refL_b  # refL_b was set to None above, use the bar from the range
            flipLL_lock = True
            flipHH_lock = False

            if verbose or in_focus(ts_i):
                print(f"\n  >>> HL FLIP (bull->bear) at bar {i} ({ts_to_utc(ts_i)})")
                print(f"      low={low_i} <= refL_p={refL_p_old}")
                print(f"      lastFH_p={lastFH_p}")
                print(f"      bias: {bias_str(old_bias)} -> BEAR")
                print(f"      range = [{rLo}, {rHi}]")
                print(f"      v12: current_LL_p seeded = {current_LL_p}")
                print(f"      v12: flipLL_lock = True, flipHH_lock = False")
                print_state("Post HL FLIP state")

            if in_focus(ts_i):
                break_summary.append({
                    "bar": i,
                    "ts": ts_i,
                    "type": "HL FLIP",
                    "high": high_i,
                    "low": low_i,
                    "rHi": rHi,
                    "rLo": rLo,
                    "old_bias": bias_str(old_bias),
                    "new_bias": "BEAR",
                    "refL_p": refL_p,
                    "refH_p": refH_p,
                })

        # LH break (flip bear to bull)
        if (not newBreak
                and bias == -1
                and refH_p is not None
                and high_i >= refH_p):
            old_bias = bias
            bias = 1
            rHi = refH_p
            rLo = lastFL_p if lastFL_p is not None else low_i
            newBreak = True
            break_type = "LH FLIP"
            refH_p_old = refH_p
            refH_p = None
            refH_b = None
            structural_LL_p = None
            structural_LL_b = None
            current_LL_p = None
            current_LL_b = None
            candidate_LH_p = None
            candidate_LH_b = None
            # v12: seed current_HH from rHi, set flipHH_lock, clear flipLL_lock
            current_HH_p = rHi
            current_HH_b = refH_b  # refH_b was set to None above
            flipHH_lock = True
            flipLL_lock = False

            if verbose or in_focus(ts_i):
                print(f"\n  >>> LH FLIP (bear->bull) at bar {i} ({ts_to_utc(ts_i)})")
                print(f"      high={high_i} >= refH_p={refH_p_old}")
                print(f"      lastFL_p={lastFL_p}")
                print(f"      bias: {bias_str(old_bias)} -> BULL")
                print(f"      range = [{rLo}, {rHi}]")
                print(f"      v12: current_HH_p seeded = {current_HH_p}")
                print(f"      v12: flipHH_lock = True, flipLL_lock = False")
                print_state("Post LH FLIP state")

            if in_focus(ts_i):
                break_summary.append({
                    "bar": i,
                    "ts": ts_i,
                    "type": "LH FLIP",
                    "high": high_i,
                    "low": low_i,
                    "rHi": rHi,
                    "rLo": rLo,
                    "old_bias": bias_str(old_bias),
                    "new_bias": "BULL",
                    "refL_p": refL_p,
                    "refH_p": refH_p,
                })

        # Print bar without fractal or break if in focus and nothing happened
        if verbose and not fh and not fl and not newBreak:
            # Only print a minimal line for bars with no events
            pass

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n\n{'='*80}")
    print(f"BREAK EVENT SUMMARY (focus window {ts_to_utc(FOCUS_START)} to {ts_to_utc(FOCUS_END)})")
    print(f"{'='*80}")
    if not break_summary:
        print("  No break events in focus window.")
    else:
        for evt in break_summary:
            print(f"\n  {evt['type']} at bar {evt['bar']} | {ts_to_utc(evt['ts'])}")
            print(f"    Bar OHLC: H={evt['high']} L={evt['low']}")
            print(f"    Bias: {evt['old_bias']} -> {evt['new_bias']}")
            print(f"    Range: [{evt['rLo']}, {evt['rHi']}]")
            print(f"    refL_p={evt['refL_p']}  refH_p={evt['refH_p']}")

    print(f"\n{'='*80}")
    print(f"FINAL STATE after all bars:")
    print_state()
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
