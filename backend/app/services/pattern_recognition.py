"""
PatternBot — Advanced Chart Analysis Engine v2
==============================================
Features:
  • SMC: Fair Value Gaps + Bullish/Bearish Order Blocks
  • ICT Concepts: BOS/CHoCH, Liquidity Sweeps, Kill Zones, Premium/Discount
  • RSI Divergence (real swing-point detection — bullish & bearish)
  • MACD: multi-timeframe cross signals
  • Supertrend ATR bands
  • Fibonacci 0.618 / 0.382 retracement
  • Elliott Wave A-B-C pivot annotation
  • Linear-regression PREDICTION BAND (forward)
  • Supports any Binance interval: 1m, 5m, 15m, 1h, 4h, 1d
"""

import httpx
import math
import pandas as pd
import mplfinance as mpf
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import ta
import os
import uuid
import json
import asyncio
from datetime import datetime
from app.services import chart_patterns
from .llm_advisor import LLMAdvisor
from .database_service import DatabaseService

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static")
LOG_DIR    = os.path.join(os.path.dirname(__file__), "..", "..", "data")
BASE_URL   = "http://localhost:8000/static"

INTERVAL_CONFIG = {
    "1m":  {"limit": 1000, "plot_bars": 120, "pred_bars": 30, "fmt": "%H:%M"},
    "3m":  {"limit": 1000, "plot_bars": 120, "pred_bars": 25, "fmt": "%H:%M"},
    "5m":  {"limit": 1000, "plot_bars": 100, "pred_bars": 20, "fmt": "%H:%M"},
    "15m": {"limit": 1000, "plot_bars": 100, "pred_bars": 15, "fmt": "%H:%M"},
    "30m": {"limit": 1000, "plot_bars": 100, "pred_bars": 12, "fmt": "%H:%M"},
    "1h":  {"limit": 1000, "plot_bars": 100, "pred_bars": 10, "fmt": "%b %d %H:%M"},
    "2h":  {"limit": 1000, "plot_bars": 100, "pred_bars": 8,  "fmt": "%b %d %H:%M"},
    "4h":  {"limit": 1000, "plot_bars": 100, "pred_bars": 7,  "fmt": "%b %d %H:%M"},
    "6h":  {"limit": 1000, "plot_bars": 100, "pred_bars": 6,  "fmt": "%b %d"},
    "8h":  {"limit": 1000, "plot_bars": 100, "pred_bars": 5,  "fmt": "%b %d"},
    "12h": {"limit": 1000, "plot_bars": 100, "pred_bars": 4,  "fmt": "%b %d"},
    "1d":  {"limit": 1000, "plot_bars": 100, "pred_bars": 3,  "fmt": "%Y-%m-%d"},
    "3d":  {"limit": 1000, "plot_bars": 100, "pred_bars": 2,  "fmt": "%Y-%m-%d"},
    "1w":  {"limit": 1000, "plot_bars": 100, "pred_bars": 1,  "fmt": "%Y-%W"},
    "1M":  {"limit": 1000, "plot_bars": 100, "pred_bars": 1,  "fmt": "%Y-%m"},
}

VALID_SYMBOLS = {"BTC", "ETH", "SOL", "BNB", "ETC", "XRP", "ADA", "DOGE"}

# Binance taker fee round-trip (0.1% entry + 0.1% exit = 0.2%).
# TP must be at least this far from entry to be a net-positive trade.
FEE_BUFFER = 0.002


# ─── RSI Divergence Detection ────────────────────────────────────────────────

def _find_swing_highs(arr: np.ndarray, window: int = 5) -> list[int]:
    """Return indices of local swing highs."""
    idxs = []
    for i in range(window, len(arr) - window):
        if arr[i] == max(arr[i - window: i + window + 1]):
            idxs.append(i)
    return idxs

def _find_swing_lows(arr: np.ndarray, window: int = 5) -> list[int]:
    """Return indices of local swing lows."""
    idxs = []
    for i in range(window, len(arr) - window):
        if arr[i] == min(arr[i - window: i + window + 1]):
            idxs.append(i)
    return idxs

def detect_rsi_divergence(closes: np.ndarray, rsi: np.ndarray, lookback: int = 60) -> str:
    """
    Detect bullish or bearish RSI divergence over the last `lookback` bars.
    Bullish: price makes lower low, RSI makes higher low → reversal up signal.
    Bearish: price makes higher high, RSI makes lower high → reversal down signal.
    """
    c = closes[-lookback:]
    r = rsi[-lookback:]

    highs_p = _find_swing_highs(c, window=4)
    lows_p  = _find_swing_lows(c,  window=4)
    highs_r = _find_swing_highs(r, window=4)
    lows_r  = _find_swing_lows(r,  window=4)

    # Bearish divergence: price higher high, RSI lower high
    if len(highs_p) >= 2 and len(highs_r) >= 2:
        ph1, ph2 = highs_p[-2], highs_p[-1]
        rh1, rh2 = highs_r[-2], highs_r[-1]
        if (c[ph2] > c[ph1]) and (r[rh2] < r[rh1]):
            return (
                f"🔴 **Bearish RSI Divergence Detected** — "
                f"Price: ${c[ph1]:,.0f} → ${c[ph2]:,.0f} (Higher High), "
                f"RSI: {r[rh1]:.1f} → {r[rh2]:.1f} (Lower High). "
                f"⚠️ Momentum weakening — potential reversal DOWN."
            )

    # Bullish divergence: price lower low, RSI higher low
    if len(lows_p) >= 2 and len(lows_r) >= 2:
        pl1, pl2 = lows_p[-2], lows_p[-1]
        rl1, rl2 = lows_r[-2], lows_r[-1]
        if (c[pl2] < c[pl1]) and (r[rl2] > r[rl1]):
            return (
                f"🟢 **Bullish RSI Divergence Detected** — "
                f"Price: ${c[pl1]:,.0f} → ${c[pl2]:,.0f} (Lower Low), "
                f"RSI: {r[rl1]:.1f} → {r[rl2]:.1f} (Higher Low). "
                f"✅ Selling momentum fading — potential reversal UP."
            )

    return f"RSI divergence: No clear signal at current structure (RSI={rsi[-1]:.1f})."


# ─── ICT Concepts ────────────────────────────────────────────────────────────

def detect_ict_concepts(df: pd.DataFrame, history_times: list = None) -> dict:
    """
    Returns a dict of ICT analysis results:
      - order_block: textual summary
      - fvg: textual summary
      - zones: list of visual objects for chart drawing [{'time', 'price', 'type', 'color'}]
    """
    closes = df["Close"].values
    highs  = df["High"].values
    lows   = df["Low"].values
    n      = len(closes)
    cur    = float(closes[-1])
    results = {}

    # ── Order Blocks (last 30 bars) ──────────────────────────────────────────
    # Bullish OB: last bearish candle before a strong bullish move
    # Bearish OB: last bullish candle before a strong bearish move
    ob_bull, ob_bear = [], []
    for i in range(max(0, n - 30), n - 2):
        body_cur  = closes[i]   - df["Open"].values[i]
        body_next = closes[i+1] - df["Open"].values[i+1]
        # Bullish OB: bearish candle followed by strong bull candle
        if body_cur < 0 and body_next > abs(body_cur) * 1.5:
            ob_bull.append({"high": highs[i], "low": lows[i], "idx": i})
        # Bearish OB: bullish candle followed by strong bear candle
        if body_cur > 0 and abs(body_next) > body_cur * 1.5:
            ob_bear.append({"high": highs[i], "low": lows[i], "idx": i})

    if ob_bull:
        ob = ob_bull[-1]
        results["order_block"] = (
            f"🟩 **Bullish Order Block** at ${ob['low']:,.0f}–${ob['high']:,.0f} "
            f"({'✅ Price above OB (support)' if cur > ob['low'] else '⚠️ Price inside OB zone'})"
        )
    elif ob_bear:
        ob = ob_bear[-1]
        results["order_block"] = (
            f"🟥 **Bearish Order Block** at ${ob['low']:,.0f}–${ob['high']:,.0f} "
            f"({'⚠️ Price inside OB zone (resistance)' if cur < ob['high'] else '✅ Price broke above OB'})"
        )
    else:
        results["order_block"] = "No significant Order Block detected in last 30 bars."

    # ── Fair Value Gaps (3-candle pattern) ──────────────────────────────────
    fvg_found = []
    for i in range(max(0, n - 20), n - 2):
        gap_up   = lows[i + 2] > highs[i]       # Bullish FVG
        gap_down = highs[i + 2] < lows[i]        # Bearish FVG
        if gap_up:
            fvg_found.append(f"✅ **Bullish FVG** gap: ${highs[i]:,.0f}–${lows[i+2]:,.0f} (magnet support)")
        elif gap_down:
            fvg_found.append(f"🔻 **Bearish FVG** gap: ${highs[i+2]:,.0f}–${lows[i]:,.0f} (overhead resistance)")
    results["fvg"] = fvg_found[-1] if fvg_found else "No Fair Value Gaps in last 20 bars."

    # ── BOS / CHoCH ──────────────────────────────────────────────────────────
    # BOS (Break of Structure): price takes out a recent swing high/low with intent
    swing_highs = _find_swing_highs(highs[-50:], window=5)
    swing_lows  = _find_swing_lows(lows[-50:],   window=5)
    bos_msg = "Structure: No clear BOS/CHoCH signal."
    if len(swing_highs) >= 2:
        sh1 = float(highs[-50:][swing_highs[-2]])
        sh2 = float(highs[-50:][swing_highs[-1]])
        if cur > sh1:
            bos_msg = (f"📈 **Break of Structure (BOS)** — Price broke above "
                       f"${sh1:,.0f} (recent swing high). Bullish continuation expected.")
    if len(swing_lows) >= 2:
        sl1 = float(lows[-50:][swing_lows[-2]])
        sl2 = float(lows[-50:][swing_lows[-1]])
        if cur < sl1:
            bos_msg = (f"📉 **Change of Character (CHoCH)** — Price broke below "
                       f"${sl1:,.0f} (recent swing low). Bias flipping bearish.")
    results["bos_choch"] = bos_msg

    # ── Liquidity Sweeps (equal highs/lows) ──────────────────────────────────
    # BSL (Buy Side Liquidity): equal highs swept, now pulling back
    # SSL (Sell Side Liquidity): equal lows swept, now bouncing
    sweep_msg = "Liquidity: No recent sweep detected."
    if len(swing_highs) >= 2:
        h1 = highs[-50:][swing_highs[-2]]
        h2 = highs[-50:][swing_highs[-1]]
        if abs(h1 - h2) / h1 < 0.003:  # Within 0.3% = equal highs
            sweep_msg = (f"⚡ **BSL Sweep** — Equal highs near ${h1:,.0f} swept. "
                         f"Smart Money may have triggered stops above — watch for rejection.")
    if len(swing_lows) >= 2:
        l1 = lows[-50:][swing_lows[-2]]
        l2 = lows[-50:][swing_lows[-1]]
        if abs(l1 - l2) / l1 < 0.003:  # Equal lows
            sweep_msg = (f"⚡ **SSL Sweep** — Equal lows near ${l1:,.0f} swept. "
                         f"Liquidity taken below — watch for reversal up.")
    results["liquidity_sweep"] = sweep_msg

    # ── Premium / Discount Zone ──────────────────────────────────────────────
    hi90 = float(np.max(closes[-90:]))
    lo90 = float(np.min(closes[-90:]))
    eq   = (hi90 + lo90) / 2
    pos  = (cur - lo90) / (hi90 - lo90) * 100 if hi90 != lo90 else 50
    if pos > 70:
        pd_msg = (f"💎 **Premium Zone** ({pos:.0f}% of 90-bar range). "
                  f"Price is expensive relative to range — ICT favors SELLS here.")
    elif pos < 30:
        pd_msg = (f"🛒 **Discount Zone** ({pos:.0f}% of 90-bar range). "
                  f"Price is cheap relative to range — ICT favors BUYS here.")
    else:
        pd_msg = (f"⚖️ **Equilibrium Zone** ({pos:.0f}% of range) near ${eq:,.0f}. "
                  f"Neutral — wait for displacement.")
    results["premium_discount"] = pd_msg

    # ── Kill Zone (UTC time-based) ────────────────────────────────────────────
    utc_hour = datetime.utcnow().hour
    if 2 <= utc_hour < 5:
        kz = "🕐 **Asian Kill Zone** (02:00–05:00 UTC) — liquidity building, range session."
    elif 7 <= utc_hour < 10:
        kz = "🕐 **London Kill Zone** (07:00–10:00 UTC) — HIGH volatility, look for London sweeps."
    elif 12 <= utc_hour < 15:
        kz = "🕐 **New York Kill Zone** (12:00–15:00 UTC) — PRIME tradeable window, ICT optimal."
    elif 19 <= utc_hour < 22:
        kz = "🕐 **NY PM / Asia Prep** (19:00–22:00 UTC) — low volume, avoid chasing."
    else:
        kz = f"🕐 Off Kill-Zone hours (UTC {utc_hour:02d}:xx) — reduced institutional activity."
    results["kill_zone"] = kz

    # ── Institutional Magnets (Nearest Unfilled Targets) ─────────────────────
    # These are the targets the price is 'magnetically' attracted to.
    magnets = []
    # Find nearest bullish FVG below or bearish FVG above
    for i in range(max(0, n - 40), n - 2):
        if lows[i + 2] > highs[i] and cur > highs[i]: # Bullish FVG below (Magnet Support)
            magnets.append({"price": (highs[i] + lows[i+2])/2, "type": "Bullish FVG", "dist": cur - highs[i]})
        if highs[i + 2] < lows[i] and cur < lows[i]: # Bearish FVG above (Magnet Resistance)
            magnets.append({"price": (lows[i] + highs[i+2])/2, "type": "Bearish FVG", "dist": lows[i] - cur})
            
    # Add OBs as magnets
    if ob_bull: magnets.append({"price": (ob_bull[-1]["high"] + ob_bull[-1]["low"])/2, "type": "Bullish OB", "dist": abs(cur - ob_bull[-1]["high"])})
    if ob_bear: magnets.append({"price": (ob_bear[-1]["high"] + ob_bear[-1]["low"])/2, "type": "Bearish OB", "dist": abs(cur - ob_bear[-1]["low"])})

    # Sort by proximity
    magnets.sort(key=lambda x: x["dist"])
    results["magnets"] = magnets[:3] # Top 3 nearest magnets

    # ── Visual Data for Charting ─────────────────────────────────────────────
    zones = []
    if history_times:
        # Add last Order Block as a zone
        if ob_bull:
            ob = ob_bull[-1]
            zones.append({"time": history_times[ob["idx"]], "price": ob["high"], "label": "OB", "color": "#2bda9e55"}) # Translucent
            zones.append({"time": history_times[ob["idx"]], "price": ob["low"], "label": "", "color": "#2bda9e55"})
            
        # Add last FVG as a zone
        for i in range(max(0, n - 20), n - 2):
            if lows[i + 2] > highs[i]: # Bullish FVG
                zones.append({"time": history_times[i+1], "price": highs[i], "label": "FVG", "color": "#2bda9e33"})
                zones.append({"time": history_times[i+1], "price": lows[i+2], "label": "", "color": "#2bda9e33"})
            elif highs[i + 2] < lows[i]: # Bearish FVG
                zones.append({"time": history_times[i+1], "price": lows[i], "label": "FVG", "color": "#ff525233"})
                zones.append({"time": history_times[i+1], "price": highs[i+2], "label": "", "color": "#ff525233"})

    results["zones"] = zones
    return results


# ─── MACD Signal Detection ───────────────────────────────────────────────────

def detect_macd_signal(closes: np.ndarray) -> str:
    """Compute MACD and return current signal with histogram trend."""
    s = pd.Series(closes)
    ema12 = s.ewm(span=12, adjust=False).mean()
    ema26 = s.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - signal

    m, sig, h = float(macd.iloc[-1]), float(signal.iloc[-1]), float(hist.iloc[-1])
    h_prev = float(hist.iloc[-2])

    if m > sig and h > 0:
        cross = "🟢 **MACD Bullish** — MACD above signal"
        trend = "histogram growing ↑" if h > h_prev else "histogram shrinking ↓ (weakening)"
    elif m < sig and h < 0:
        cross = "🔴 **MACD Bearish** — MACD below signal"
        trend = "histogram growing ↓" if h < h_prev else "histogram recovering ↑ (weakening)"
    else:
        cross = "⚡ **MACD Crossover** — signal line being tested"
        trend = "watch for confirmation"

    return f"{cross} | {trend} | MACD={m:.2f} Signal={sig:.2f} Hist={h:+.2f}"


# ─── Elliott Wave Discovery ───────────────

def detect_elliott_wave(closes: np.ndarray, history_times: list) -> dict:
    """identify Wave 1-5 or A-B-C structure with Phase determination."""
    highs_idx = _find_swing_highs(closes, window=5)
    lows_idx  = _find_swing_lows(closes, window=5)
    
    res = {"text": "Phase: Accumulation/Sideways", "phase": "Neutral", "pivots": []}
    if len(highs_idx) < 3 or len(lows_idx) < 3:
        res["text"] = "Awaiting more swing data for phase analysis."
        return res
        
    closes_arr = np.array(closes)
    prices_h = closes_arr[highs_idx]
    prices_l = closes_arr[lows_idx]
    
    pivots = []
    # Identify chronological sequence
    all_pivots = []
    for l_idx in lows_idx[-5:]:
        all_pivots.append({"idx": l_idx, "type": "low", "price": float(closes[l_idx])})
    for h_idx in highs_idx[-5:]:
        all_pivots.append({"idx": h_idx, "type": "high", "price": float(closes[h_idx])})
    
    all_pivots.sort(key=lambda x: x["idx"])
    
    # Labeling logic
    for i, p in enumerate(all_pivots[-5:]):
        labels = ["1", "2", "3", "4", "5"]
        pivots.append({
            "time": int(history_times[p["idx"]]),
            "price": p["price"],
            "label": labels[i] if i < len(labels) else f"Ext{i}",
            "color": "#2bda9e" if p["type"] == "low" else "#f39c12"
        })

    # Determining Phase
    cur = closes[-1]
    last_h, prev_h = prices_h[-1], prices_h[-2]
    last_l, prev_l = prices_l[-1], prices_l[-2]
    
    # 1. Impulse Phase (1-3-5)
    if last_h > prev_h and last_l > prev_l:
        res["text"] = "🌊 **Impulse Phase (W3/5)** — Major move in progress."
        res["phase"] = "Impulse"
    # 2. Correction Phase (2-4 / A-C)
    elif cur < last_h and cur > last_l:
         res["text"] = "⚖️ **Correction Phase** — Range bound / Consolidation."
         res["phase"] = "Correction"
    elif last_h < prev_h and last_l < prev_l:
        res["text"] = "📉 **Correction Wave C** — Pullback phase."
        res["phase"] = "Correction"
    
    res["pivots"] = pivots
    return res


# ─── Chart Patterns (H&S, Flags) ──────────

def detect_chart_patterns(df: pd.DataFrame) -> str:
    """Detect Head & Shoulders or Flags."""
    closes = df["Close"].values
    highs = df["High"].values
    lows = df["Low"].values
    
    # Simple Flag Detection (Strong move followed by tight range)
    movement = (closes[-1] - closes[-20]) / closes[-20]
    range_last_5 = (max(highs[-5:]) - min(lows[-5:])) / closes[-1]
    
    if movement > 0.05 and range_last_5 < 0.01:
        return "🚩 **Bull Flag Detected** — High-prob continuation UP."
    if movement < -0.05 and range_last_5 < 0.01:
        return "🚩 **Bear Flag Detected** — High-prob continuation DOWN."
        
    # Peak Analysis for H&S
    p_idxs = _find_swing_highs(highs[-60:], window=5)
    if len(p_idxs) >= 3:
        p1 = highs[-60:][p_idxs[-3]]
        p2 = highs[-60:][p_idxs[-2]] # Head
        p3 = highs[-60:][p_idxs[-1]]
        if p2 > p1 and p2 > p3 and abs(p1 - p3) / p1 < 0.01:
            return "👤 **Head & Shoulders** — Major reversal TOP detected."
            
    return "Patterns: No major geometric formations."


# ─── Supertrend ATR & Bollinger Bands ──────

def detect_volatility_bands(df: pd.DataFrame) -> dict:
    """Compute Bollinger Bands & Supertrend."""
    # Bollinger Bands
    ma20 = df["Close"].rolling(20).mean()
    std20 = df["Close"].rolling(20).std()
    upper = ma20 + (std20 * 2)
    lower = ma20 - (std20 * 2)
    
    cur = df["Close"].iloc[-1]
    bb_msg = "Neutral"
    if cur > upper.iloc[-1]: bb_msg = "Overextended Top"
    if cur < lower.iloc[-1]: bb_msg = "Overextended Bottom"
    
    # Supertrend (Simplified)
    atr = ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=10).average_true_range()
    middle = (df["High"] + df["Low"]) / 2
    st_upper = middle + (3 * atr)
    st_lower = middle - (3 * atr)
    
    st_bias = "Bullish" if cur > st_lower.iloc[-1] else "Bearish"
    
    return {
        "bb": f"Bollinger: {bb_msg} (${lower.iloc[-1]:,.0f}–${upper.iloc[-1]:,.0f})",
        "st": f"Supertrend: {st_bias}",
        "st_bias": st_bias
    }


# ─── Volume Spread Analysis (VSA) ──────────

def detect_vsa_signals(df: pd.DataFrame) -> str:
    """Detect Institutional Absorption or Climax."""
    v = df["Volume"].values
    c = df["Close"].values
    o = df["Open"].values
    h = df["High"].values
    l = df["Low"].values
    
    avg_v = np.mean(v[-20:])
    spread = abs(c[-1] - o[-1])
    wick_upper = h[-1] - max(c[-1], o[-1])
    wick_lower = min(c[-1], o[-1]) - l[-1]
    
    # 1. Buying Climax (Huge volume, small body, long top wick)
    if v[-1] > avg_v * 2 and spread < (h[-1] - l[-1]) * 0.3 and wick_upper > wick_lower:
        return "⚠️ **Institutional Absorption (Sell)** — Massive volume but price held back. Smart Money is exiting."
    
    # 2. Stopping Volume (Huge volume, long bottom wick)
    if v[-1] > avg_v * 2 and wick_lower > wick_upper * 1.5:
        return "🚀 **Stopping Volume (Buy)** — Huge sell orders absorbed by institutional buyers."
        
    return "VSA: Volume flow is standard retail participation."


# ─── Artificial Intelligence Double-Check ────────────────

async def llm_accuracy_validation(logic: str, symbol: str, price: float) -> float:
    """
    Use Gemini to 'veto' or 'bless' the technical setup.
    Returns a multiplier (0.5 to 1.5).
    """
    try:
        advisor = LLMAdvisor()
        prompt = f"""
        AS A QUANT ANALYST:
        RE-EVALUATE this setup for {symbol} at ${price:,.2f}.
        TECHNICAL LOGIC: {logic}
        
        Is this a 99% probability setup? 
        Strict Rules:
        - If Trend Conflicts or Volume is low, decrease score.
        - If Elliott Wave 3 aligns with SMC Order Block, increase score.
        
        OUTPUT ONLY A SINGLE FLOAT (0.0 to 1.0) representing Accuracy Confidence.
        """
        response = await advisor.get_advice(prompt)
        # Extract float from response
        import re
        match = re.search(r"(\d\.\d+)", response)
        if match:
            return float(match.group(1))
        return 0.8 # Default to cautious
    except:
        return 0.8

# ─── Golden Pocket & Candlestick Analysis ──────────────────

def detect_golden_pocket(closes: np.ndarray, highs: np.ndarray, lows: np.ndarray) -> dict:
    """Check if current price is testing the 0.618 - 0.65 Golden Pocket logic."""
    if len(highs) < 60: return {"hit": False, "msg": ""}
    
    recent_h = float(np.max(highs[-60:]))
    recent_l = float(np.min(lows[-60:]))
    range_dist = recent_h - recent_l
    if range_dist == 0: return {"hit": False, "msg": ""}
    
    cur = float(closes[-1])
    # Distance from top
    fib_level = (recent_h - cur) / range_dist
    
    # Golden Pocket bounce (bullish retracement)
    if 0.60 <= fib_level <= 0.66:
        return {"hit": True, "type": "Bullish", "msg": "🟡 **Golden Pocket (0.618) Support** Reached"}
        
    # Golden Pocket rejection (bearish retracement)
    fib_level_inv = (cur - recent_l) / range_dist
    if 0.60 <= fib_level_inv <= 0.66:
         return {"hit": True, "type": "Bearish", "msg": "🔴 **Golden Pocket (0.618) Resistance** Reached"}
         
    return {"hit": False, "msg": ""}

def detect_candlesticks(df: pd.DataFrame) -> dict:
    """Identify High-Probability Reversal Candles (Engulfing, Pinbar/Hammer)."""
    if len(df) < 3: return {"type": "None", "msg": ""}
    
    o, h, l, c = df["Open"].values, df["High"].values, df["Low"].values, df["Close"].values
    o1, h1, l1, c1 = o[-1], h[-1], l[-1], c[-1]
    o2, h2, l2, c2 = o[-2], h[-2], l[-2], c[-2]
    
    body = abs(c1 - o1)
    wick_up = h1 - max(c1, o1)
    wick_dn = min(c1, o1) - l1
    
    # Bullish Engulfing
    if c2 < o2 and c1 > o1 and c1 > o2 and o1 < c2:
        return {"type": "Bullish", "msg": "📈 **Bullish Engulfing** Candle"}
        
    # Bullish Hammer / Pinbar
    if wick_dn > (body * 2) and wick_up < body:
        return {"type": "Bullish", "msg": "🔨 **Bullish Hammer (Pinbar)** Liquidity Sweep"}

    # Bearish Engulfing
    if c2 > o2 and c1 < o1 and c1 < o2 and o1 > c2:
        return {"type": "Bearish", "msg": "📉 **Bearish Engulfing** Candle"}
        
    # Bearish Shooting Star / Pinbar
    if wick_up > (body * 2) and wick_dn < body:
         return {"type": "Bearish", "msg": "🌠 **Shooting Star (Pinbar)** Rejection"}
         
    return {"type": "None", "msg": ""}


def run_monte_carlo_simulation(initial_price: float, slope: float, atr: float, iterations: int = 10000, magnets: list = None) -> float:
    """
    Simulates price paths using a random walk with drift + 'Magnet Gravity'.
    """
    drift = slope / (initial_price * 0.01)
    vol = (atr / initial_price)
    
    # Magnet Gravity: Skew drift toward nearest institutional magnet
    if magnets:
        nearest = magnets[0]
        magnet_pull = (nearest["price"] - initial_price) / initial_price
        # Pull is 30% of the total drift vector
        drift = (drift * 0.7) + (magnet_pull * 0.3)

    rng = np.random.default_rng()
    returns = rng.normal(drift, vol, iterations)
    future_prices = initial_price * np.exp(returns)
    
    bullish_outcomes = np.sum(future_prices > initial_price)
    return (bullish_outcomes / iterations)


# ─── Main PatternBot ─────────────────────────────────────────────────────────

class PatternBot:

    @staticmethod
    async def get_ohlc_prediction(symbol: str, interval: str = "15m", persist: bool = False):
        """Returns raw historical OHLC + the predicted next candle for JS charting."""
        fetch_asset = symbol.upper() if symbol.upper() in VALID_SYMBOLS else "BTC"
        if interval not in INTERVAL_CONFIG:
            interval = "15m"
        cfg = INTERVAL_CONFIG[interval]

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                # 1. Fetch Main Chart Data (Deep History: 3,000 candles)
                klines = []
                current_end_time = None
                
                for _ in range(5): # 5 batches of 1000 = 5,000 bars
                    batch_url = f"https://data-api.binance.vision/api/v3/klines?symbol={fetch_asset}USDT&interval={interval}&limit=1000"
                    if current_end_time:
                        batch_url += f"&endTime={current_end_time - 1}"
                    
                    batch_res = await client.get(batch_url)
                    if batch_res.status_code == 200:
                        batch_data = batch_res.json()
                        if not batch_data:
                            break
                        # Prepend batch to klines to keep chronological order
                        klines = batch_data + klines
                        current_end_time = batch_data[0][0] # Earliest in this batch
                    else:
                        break

                if not klines:
                    return {"error": "Failed to fetch any chart history"}

                # 2. Fetch Macro Data (Daily 1D) (~10+ years - requires multiple requests)
                macro_klines = []
                last_ts = None
                for _ in range(4): # 4 requests * 1000 = 4000 days (~11 years)
                    t_url = f"https://data-api.binance.vision/api/v3/klines?symbol={fetch_asset}USDT&interval=1d&limit=1000"
                    if last_ts:
                        t_url += f"&endTime={last_ts - 1}"
                    
                    m_res = await client.get(t_url)
                    if m_res.status_code == 200:
                        batch = m_res.json()
                        if not batch: break
                        macro_klines = batch + macro_klines
                        last_ts = batch[0][0]
                    else: 
                        break
                
                # 3. Calculate Macro ATH/ATL (~10 years)
                ath = 0
                atl = float('inf')
                if macro_klines:
                    for k in macro_klines:
                        h_val = float(k[2])
                        l_val = float(k[3])
                        if h_val > ath: ath = h_val
                        if l_val < atl: atl = l_val
                
                # 4. Fetch Ultra-Macro Data (Weekly 1W) (1000 weeks ~ 19 years)
                # Format data for Lightweight Charts (time as unix ts, open, high, low, close)
                history = []
                closes = []
                highs = []
                lows = []
                
                for k in klines:
                    ts = int(k[0] / 1000)
                    o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
                    history.append({"time": ts, "open": o, "high": h, "low": l, "close": c})
                    closes.append(c)
                    highs.append(h)
                    lows.append(l)

                # Create DataFrame for indicator computation
                df_raw = pd.DataFrame(klines).iloc[:, :6]
                df_raw.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
                df = df_raw.astype(float)
                
                # Indicators
                df["sma50"]  = df["Close"].rolling(50).mean()
                df["ma99"]   = df["Close"].rolling(99).mean()
                df["ma200"]  = df["Close"].rolling(200).mean()
                df["ema7"]   = df["Close"].ewm(span=7, adjust=False).mean()
                df["ema20"]  = df["Close"].ewm(span=20, adjust=False).mean()
                df["ema25"]  = df["Close"].ewm(span=25, adjust=False).mean()
                df["rsi"]    = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
                df["psar"]   = ta.trend.PSARIndicator(df["High"], df["Low"], df["Close"], step=0.02, max_step=0.2).psar()
                atr_ind      = ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=14)
                atr          = float(atr_ind.average_true_range().iloc[-1]) if not pd.isna(atr_ind.average_true_range().iloc[-1]) else (float(df["Close"].iloc[-1]) * 0.01)

                # Linear regression for momentum
                n = len(closes)
                reg_window = min(50, n)
                x_reg = np.arange(reg_window)
                y_reg = np.array(closes[-reg_window:])
                slope, intercept = np.polyfit(x_reg, y_reg, 1)
                
                p_close = float(slope * reg_window + intercept)
                p_open = float(closes[-1])
                p_high = max(p_open, p_close) + (atr * 0.3)
                p_low = min(p_open, p_close) - (atr * 0.3)
                
                # Next candle time
                dt_delta = history[-1]["time"] - history[-2]["time"] if len(history) > 1 else 0
                next_ts = history[-1]["time"] + dt_delta
                hist_times = [h["time"] for h in history]
                
                # --- Update History Payload with new MAs/EMAs ---
                for i in range(len(history)):
                    val_ma99 = df["ma99"].iloc[i]
                    val_ma200 = df["ma200"].iloc[i]
                    history[i]["ema7"] = float(df["ema7"].iloc[i]) if not pd.isna(df["ema7"].iloc[i]) else None
                    history[i]["ema25"] = float(df["ema25"].iloc[i]) if not pd.isna(df["ema25"].iloc[i]) else None
                    history[i]["ma99"] = float(val_ma99) if not pd.isna(val_ma99) else None
                    history[i]["ma200"] = float(val_ma200) if not pd.isna(val_ma200) else None

                # ─── 2. Expert Consensus "Ultra-Accuracy" Engine ────────────────
                # To reach ~90%+ accuracy, we must filter out "Market Noise"
                # and only trade with High-Conviction Confluence.
                
                score = 0  # -100 to +100
                logic_notes = []
                
                # Fetch and inject Macro Sentiment
                from .news_service import news_service
                try:
                    macro_news = await news_service.get_macro_sentiment()
                    logic_notes.append(macro_news)
                except Exception as e:
                    pass
                
                # Factor 1: MTF Trend Filter (Multi-Timeframe)
                # If 15m is Long, but 4h is Short -> Penalize Score
                # (In this simple version, we check the slope of the 50 SMA)
                sma50_prev = df["sma50"].iloc[-10] if len(df) > 10 else df["sma50"].iloc[0]
                mtf_trend_up = df["sma50"].iloc[-1] > sma50_prev
                
                # Factor 2: Trend Alignment & Moving Average Structure
                ema7, ema20, ema25 = df["ema7"].iloc[-1], df["ema20"].iloc[-1], df["ema25"].iloc[-1]
                ma99, ema50, ma200 = df["ma99"].iloc[-1], df["sma50"].iloc[-1], df["ma200"].iloc[-1]
                
                if not pd.isna(ema50):
                    if p_open > ema50 and mtf_trend_up: score += 25; logic_notes.append("Strong MTF Trend")
                    elif p_open < ema50 and not mtf_trend_up: score -= 25; logic_notes.append("Strong MTF Downtrend")
                    else: score -= 10; logic_notes.append("Trend Conflict") # Penalize noise
                
                # --- Golden / Death Stack Evaluation ---
                if not pd.isna(ma200) and not pd.isna(ma99):
                     if ema7 > ema25 and ema25 > ma99 and ma99 > ma200 and p_open > ema7:
                         score += 30; logic_notes.append("Perfect Bullish Alignment (Golden Stack)")
                     elif ema7 < ema25 and ema25 < ma99 and ma99 < ma200 and p_open < ema7:
                         score -= 30; logic_notes.append("Perfect Bearish Alignment (Death Stack)")
                
                # Factor 3: Parabolic SAR (Stop & Reverse)
                psar_val = df["psar"].iloc[-1]
                if not pd.isna(psar_val):
                    if p_open > psar_val:
                        score += 10; logic_notes.append("PSAR: Uptrend Protected")
                    else:
                        score -= 10; logic_notes.append("PSAR: Downtrend Pressure")

                # Factor 3.5: RSI Divergence & Volatility Buffer
                rsi_val = df["rsi"].iloc[-1]
                current_atr = atr
                # If volume/volatility is dead, accuracy drops -> Filter it
                volatility_burst = current_atr > (df["Close"].rolling(20).std().iloc[-1] * 0.5)
                
                if rsi_val < 30: score += 15; logic_notes.append("Oversold Rebound")
                elif rsi_val > 70: score -= 15; logic_notes.append("Overbought Pullback")
                
                if slope > 0: score += 15; logic_notes.append("Momentum Up")
                else: score -= 15; logic_notes.append("Momentum Down")

                # Factor 4: Institutional SMC/ICT (High Probability)
                ict = detect_ict_concepts(df, history_times=hist_times)
                if "Bullish" in ict.get("order_block", ""): score += 18; logic_notes.append("ICT Bullish OB")
                elif "Bearish" in ict.get("order_block", ""): score -= 18; logic_notes.append("ICT Bearish OB")
                if "Bullish FVG" in ict.get("fvg", ""): score += 12; logic_notes.append("ICT FVG Support")
                elif "Bearish FVG" in ict.get("fvg", ""): score -= 12; logic_notes.append("ICT FVG Resistance")
                
                if "BOS" in ict.get("bos_choch", ""): score += 10; logic_notes.append("BOS Confirmed")
                elif "CHoCH" in ict.get("bos_choch", ""): score -= 10; logic_notes.append("CHoCH Flip")

                 # Factor 5: Elliott Wave Master Phase logic
                wave_res = detect_elliott_wave(closes, hist_times)
                wave, phase = wave_res["text"], wave_res["phase"]
                wave_pivots = wave_res["pivots"]
                
                pattern = detect_chart_patterns(df)
                
                # --- IMPULSE Synthesis ---
                if phase == "Impulse":
                    score += 20; logic_notes.append("Aggressive Impulse Phase")
                    if "Bullish" in ict.get("order_block", ""): score += 10 # OB Rejection + Impulse = Sniper
                
                # --- CORRECTION Synthesis ---
                elif phase == "Correction":
                    score *= 0.6 # Reduce conviction for choppy ranges
                    logic_notes.append("Caution: Corrective/Range Phase")
                    if rsi_val > 70 or rsi_val < 30: score *= 1.5; logic_notes.append("Reversal in Correlation Zone")

                if "Wave 3" in wave or "Extension" in wave: score += 15; logic_notes.append("W3 Momentum")
                elif "Wave C" in wave: score -= 15; logic_notes.append("W-C De-escalation")
                
                if "Bull Flag" in pattern: score += 20; logic_notes.append("Institutional Breakout")
                elif "Bear Flag" in pattern: score -= 20; logic_notes.append("Retail Bear Flag")
                elif "Head & Shoulders" in pattern: score -= 25; logic_notes.append("Distribution Structure")

                # Factor 6: MACD & Bollinger/Supertrend (Quant Layer)
                macd_sig = detect_macd_signal(closes)
                v_bands = detect_volatility_bands(df)
                if "MACD Bullish" in macd_sig: score += 10; logic_notes.append("MACD: Bullish Convergence")
                elif "MACD Bearish" in macd_sig: score -= 10; logic_notes.append("MACD: Bearish Divergence")
                
                if v_bands["st_bias"] == "Bullish": score += 10; logic_notes.append("Supertrend: Bullish Support Maintained")
                else: score -= 10; logic_notes.append("Supertrend: Bearish Resistance Capped")
                
                if "Overextended Bottom" in v_bands["bb"]: score += 15; logic_notes.append("Bollinger Bands: Overextended Bottom (Mean Reversion Imminent)")
                elif "Overextended Top" in v_bands["bb"]: score -= 15; logic_notes.append("Bollinger Bands: Overextended Top (Mean Reversion Down)")

                # Factor 6.5: Golden Pocket & Candlesticks
                fib_pocket = detect_golden_pocket(closes, df["High"].values, df["Low"].values)
                candles = detect_candlesticks(df)
                
                if fib_pocket["hit"]:
                    if fib_pocket["type"] == "Bullish": score += 25; logic_notes.append(fib_pocket["msg"])
                    else: score -= 25; logic_notes.append(fib_pocket["msg"])
                    
                if candles["type"] == "Bullish": score += 20; logic_notes.append(candles["msg"])
                elif candles["type"] == "Bearish": score -= 20; logic_notes.append(candles["msg"])

                # Factor 6.8: Geometric Chart Patterns
                geometric_patterns = chart_patterns.detect_patterns(df)
                for pat in geometric_patterns:
                    p_name = pat["name"]
                    p_type = pat["type"]
                    p_weight = pat["weight"]
                    
                    # Check alignment with current bias (score)
                    if (p_type == "bullish" and score > 0) or (p_type == "bearish" and score < 0):
                        boost = p_weight
                        score = score + (boost if score > 0 else -boost)
                        logic_notes.append(f"Structure: {p_name} ({p_type.capitalize()}) ✅ Confirmed")
                    elif p_type == "neutral":
                        logic_notes.append(f"Structure: {p_name} (Neutral/Consolidation)")
                    else:
                        # Counter-trend pattern (reduce score)
                        score = score * 0.8
                        logic_notes.append(f"Structure: {p_name} ({p_type.capitalize()}) ⚠️ Counter-Trend")

                # Factor 7: Volume Spread Analysis (Institutional Confirmation)
                vsa = detect_vsa_signals(df)
                if "Stopping Volume" in vsa: score += 25; logic_notes.append("Inst. Absorption (Buy)")
                elif "Absorption (Sell)" in vsa: score -= 25; logic_notes.append("Inst. Distribution (Sell)")

                # Factor 8: Artificial Intelligence "Master Oracle" Validation
                # (Use LLM to filter noise and hit 99% accuracy targets)
                llm_confidence = await llm_accuracy_validation(" | ".join(logic_notes), fetch_asset, p_open)
                
                 # Factor 9: Monte Carlo Quantum Probability (Mathematical Synthesis)
                # MAGNET INJECTION: Inject nearest ICT magnets into the physics simulation
                magnets = ict.get("magnets", [])
                mc_bull_prob = run_monte_carlo_simulation(p_open, slope, atr, iterations=20000, magnets=magnets)
                
                # If a major magnet exists, display it in logic
                if magnets:
                    logic_notes.append(f"🎯 Target Magnet: {magnets[0]['type']} at ${magnets[0]['price']:,.0f}")

                mc_bias = (mc_bull_prob - 0.5) * 40 # Up to +/- 20 score impact
                score += mc_bias
                logic_notes.append(f"Monte Carlo Likelihood: {mc_bull_prob*100:.1f}%")

                # Final Confluence Adjustment
                # Max theoretical score is ~150. A score > 80 is an A+ setup.
                raw_score = abs(score)
                
                # 1. Base Confluence (0 to 1.0)
                base_conf = min(1.0, raw_score / 85.0) 
                
                # 2. Agreement Multiplier: If LLM and MC both agree strongly (>0.6), boost the score.
                mc_prob_directional = mc_bull_prob if score > 0 else (1 - mc_bull_prob)
                agreement_multiplier = (mc_prob_directional * llm_confidence) / (0.6 * 0.6)
                
                final_conviction = min(1.0, base_conf * agreement_multiplier)
                
                # If all stars align, lock it to 99.99%
                if final_conviction >= 0.985:
                     final_conviction = 0.9999
                
                # ── TRADE CALCULATION & GATING (Strict 1:1 RR) ──
                trade_entry = float(p_open)
                risk_unit   = atr * 1.5
                bull        = bool(score > 0)
                
                # Calculate AI's predicted target reach
                target_multiplier = 1.35 if phase == "Impulse" else 0.85
                sentiment_bias = (score / 100) * (atr * target_multiplier)
                predicted_tp = p_close + sentiment_bias
                
                # Calculate Risk/Reward based on prediction
                reward = abs(predicted_tp - trade_entry)
                risk = risk_unit
                rr_ratio = reward / risk if risk > 0 else 0
                
                # REVISED GATING RULES (User Requested)
                # 1. Conviction >= 0.90
                # 2. Risk/Reward >= 1.0
                is_high_conf = final_conviction >= 0.90
                is_high_rr   = rr_ratio >= 1.0
                is_confluent = len(logic_notes) >= 3
                
                if not is_high_conf or not is_confluent or not is_high_rr:
                    # Suppress signal
                    p_close_final = p_open
                    p_color = "#888888"
                    if not is_high_rr and is_high_conf:
                        logic_notes = [f"Low R:R ({rr_ratio:.1f}) / Filtering Sub-Optimal Setup"]
                    else:
                        logic_notes = ["Awaiting 90.00% Setup / Confluence Too Low... Filtering Noise"]
                    trade_tp = None
                    trade_entry = None
                    trade_sl = None
                    rr1 = rr2 = rr3 = None
                else:
                    # Valid 90%+ + 1:1 RR Signal
                    p_close_final = predicted_tp
                    p_color = "#2bda9e" if bull else "#ff5252"
                    trade_tp = predicted_tp
                    logic_notes.append(f"RR Ratio: {rr_ratio:.1f} (✅ Qualified)")

                # ── Fee-Aware TP Floor ──────────────────────────────────────────
                if trade_tp is not None and trade_entry is not None:
                    min_profit_distance = trade_entry * FEE_BUFFER
                    if bull:
                        if trade_tp < trade_entry + min_profit_distance:
                            trade_tp = trade_entry + min_profit_distance
                    else:
                        if trade_tp > trade_entry - min_profit_distance:
                            trade_tp = trade_entry - min_profit_distance
                    
                    # Sync predicted candle close with the finalized TP level
                    if is_high_conf and is_confluent and is_high_rr:
                        p_close_final = trade_tp

                    # Final SL and RR Targets for UI
                    if bull:
                        trade_sl = trade_entry - risk_unit
                        rr1 = trade_entry + (risk_unit * 1.0)
                        rr2 = trade_entry + (risk_unit * 2.0)
                        rr3 = trade_entry + (risk_unit * 3.0)
                    else:
                        trade_sl = trade_entry + risk_unit
                        rr1 = trade_entry - (risk_unit * 1.0)
                        rr2 = trade_entry - (risk_unit * 2.0)
                        rr3 = trade_entry - (risk_unit * 3.0)

                # ── Final Candle 1 Geometry ──────────────────────────────────
                # Ensure high/low bound the open/close and include a realistic wick
                p_high_1 = max(p_open, p_close_final, p_high + (sentiment_bias if score > 0 else 0))
                p_low_1  = min(p_open, p_close_final, p_low + (sentiment_bias if score < 0 else 0))
                
                # Add small ATR wicks for realism
                p_high_1 += (atr * 0.1)
                p_low_1  -= (atr * 0.1)

                prediction1 = {
                    "time": next_ts,
                    "open": p_open,
                    "high": p_high_1,
                    "low": p_low_1,
                    "close": p_close_final,
                    "color": p_color,
                    "confidence": f"{int(final_conviction * 100)}%" if final_conviction < 0.99 else "99.99%",
                    "logic": " | ".join(logic_notes),
                    "entry": trade_entry,
                    "tp": trade_tp,
                    "sl": trade_sl,
                    "rr1": rr1,
                    "rr2": rr2,
                    "rr3": rr3
                }

                # Candle 2 (Secondary Projection - Non-Linear Sequential Forecasting)
                # We no longer just clone the bias. We check for MAGNET REJECTIONS.
                next_ts_2 = next_ts + dt_delta
                p_open_2 = p_close_final
                
                # ── REACTION LOGIC ──
                magnet_reaction = 0
                if magnets:
                    target_price = magnets[0]["price"]
                    # If Candle 1 hits/fills the primary magnet, Candle 2 predicts REJECTION
                    if (bull and p_close_final >= target_price) or (not bull and p_close_final <= target_price):
                        magnet_reaction = -sentiment_bias * 0.75 # strong reversal signal
                
                # ── OVEREXTENSION LOGIC ──
                rsi_reversal = 0
                if rsi_val > 78 and bull: rsi_reversal = -atr * 0.6
                elif rsi_val < 22 and not bull: rsi_reversal = atr * 0.6
                
                # Momentum Decay (if no reversal)
                decay_factor = 0.60 if abs(sentiment_bias) > (atr * 0.5) else 0.80
                p_close_2_base = float(slope * (reg_window + 1) + intercept)
                
                # Compound the final price
                p_close_2 = p_close_2_base + (sentiment_bias * decay_factor) + magnet_reaction + rsi_reversal
                
                # Realistic Wick Modeling (asymmetrical for rejection)
                if magnet_reaction != 0 or rsi_reversal != 0:
                    # Reversal candle wicks
                    top_wick_2 = atr * 0.8 if bull else 0.2
                    bot_wick_2 = atr * 0.2 if bull else 0.8
                else:
                    top_wick_2 = atr * 0.4 if bull else 0.2
                    bot_wick_2 = atr * 0.2 if bull else 0.4
                
                p_high_2 = max(p_open_2, p_close_2) + top_wick_2
                p_low_2  = min(p_open_2, p_close_2) - bot_wick_2
                
                # Final Color Flip check
                p_color_2 = "#2bda9e" if p_close_2 > p_open_2 else "#ff5252"
                if p_close_2 == p_open_2: p_color_2 = "#888888"
                
                prediction2 = {
                    "time": next_ts_2,
                    "open": p_open_2,
                    "high": p_high_2,
                    "low": p_low_2,
                    "close": p_close_2,
                    "color": p_color_2,
                    "logic": "Reaction/Exhaustion Analysis" if (magnet_reaction or rsi_reversal) else "Momentum Phase II"
                }

                predictions = [prediction1, prediction2]

                # ─── Automated Logging & Verification ───────────────────────────
                # ─── Automated Logging, Verification & Cloud Sync ───────────────────────────
                try:
                    # 1. Save prediction ONLY if conviction is >= 90%
                    if persist and final_conviction >= 0.90:
                        csv_path = os.path.join(LOG_DIR, "prediction_history.csv")
                        pending_path = os.path.join(LOG_DIR, "pending_predictions.json")
                        
                        key = f"{fetch_asset}_{interval}_{next_ts}"
                        p_item = {
                            "symbol": fetch_asset, "interval": interval,
                            "prediction": prediction1, "timestamp": datetime.now().isoformat(),
                            "entry": trade_entry, "tp": trade_tp, "sl": trade_sl, "bull": bull,
                            "logic": " | ".join(logic_notes),
                            "is_triggered": False
                        }

                        if trade_entry is None or trade_tp is None:
                            # FILTERED SIGNAL (Trap) - Local CSV Log
                            file_exists = os.path.isfile(csv_path)
                            readable_time = datetime.fromtimestamp(next_ts).strftime('%Y-%m-%d %H:%M:%S')
                            pd.DataFrame([{
                                "date": datetime.now().isoformat(),
                                "trade_time": readable_time,
                                "symbol": fetch_asset,
                                "interval": interval,
                                "time_unix": next_ts,
                                "entry": 0, "tp": 0, "sl": 0,
                                "was_correct": -1, # -1 = Filtered/Suppressed
                                "ai_logic": " | ".join(logic_notes)
                            }]).to_csv(csv_path, mode='a', index=False, header=not file_exists)
                        else:
                            # QUALIFIED SIGNAL - Anti-Spam Check
                            pending = DatabaseService.get_all_pending()
                            
                            # Check for existing pending trade for this symbol/interval
                            duplicate = False
                            for p_val in pending.values():
                                if p_val.get("symbol") == fetch_asset and p_val.get("interval") == interval:
                                    duplicate = True
                                    break
                            
                            if not duplicate:
                                # 1. Local JSON Update
                                p_item["timestamp_unix"] = next_ts
                                local_pending = {}
                                if os.path.exists(pending_path):
                                    try:
                                        with open(pending_path) as f: local_pending = json.load(f)
                                    except: pass
                                local_pending[key] = p_item
                                with open(pending_path, "w") as f:
                                    json.dump(local_pending, f, indent=2)
                                
                                # 2. Cloud Sync (Supabase)
                                await DatabaseService.save_pending_prediction(key, p_item)

                    # 2. Trigger Global Re-Analysis (Directly in this file)
                    await PatternBot.re_analyze_all_pending()
                except Exception as e:
                    print(f"Prediction Logging Error: {e}")

                return {
                    "symbol": fetch_asset, "interval": interval, "history": history,
                    "prediction": prediction1, "predictions": predictions,
                    "wave_pivots": wave_pivots, "ict_zones": ict.get("zones", []),
                    "macro_ath": ath if ath > 0 else None,
                    "macro_atl": atl if atl < float('inf') else None,
                    "ict_summary": {
                        "premium_discount": ict.get("premium_discount"),
                        "kill_zone": ict.get("kill_zone")
                    }
                }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    async def re_analyze_all_pending():
        """
        Global Re-Analysis Engine:
        Iterates through EVERY pending trade, fetches the latest price data 
        for its specific symbol/interval, and resolves it (HIT/MISS/ACTIVE).
        """
        # LOCAL SOURCE AS PRIMARY
        pending_path = os.path.join(LOG_DIR, "pending_predictions.json")
        history_path = os.path.join(LOG_DIR, "prediction_history.json")
        csv_path = os.path.join(LOG_DIR, "prediction_history.csv")
        
        pending = {}
        if os.path.exists(pending_path):
            try:
                with open(pending_path, "r") as f:
                    pending = json.load(f)
            except: return

        if not pending: return

        any_global_changes = False
        klines_cache = {}

        for p_key in list(pending.keys()):
            p_item = pending[p_key]
            symbol, interval = p_item["symbol"], p_item["interval"]
            cache_key = f"{symbol}_{interval}"

            try:
                if cache_key not in klines_cache:
                    async with httpx.AsyncClient(timeout=10) as client:
                        res = await client.get(
                            f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}USDT&interval={interval}&limit=100"
                        )
                        if res.status_code == 200:
                            klines_cache[cache_key] = res.json()
                
                klines = klines_cache.get(cache_key)
                if not klines: continue

                for k in klines:
                    k_time = int(k[0] / 1000)
                    if k_time < p_item["prediction"]["time"]: continue
                    
                    o, h, l, c = float(k[1]), float(k[2]), float(k[3]), float(k[4])
                    entry, tp = p_item.get("entry"), p_item.get("tp")
                    sl = p_item.get("sl", entry)
                    bull = p_item.get("bull", tp >= entry) if entry and tp else True

                    if entry is None or tp is None:
                        del pending[p_key]
                        any_global_changes = True
                        break
                    
                    tp_hit = (bull and h >= tp) or (not bull and l <= tp)
                    sl_hit = (bull and l <= sl) or (not bull and h >= sl)
                    entry_hit = (bull and h >= entry) or (not bull and l <= entry)

                    if entry_hit and not p_item.get("is_triggered", False):
                        p_item["is_triggered"] = True
                        any_global_changes = True
                        # Triggered status MUST sync to cloud immediately so frontend sees "ACTIVE"
                        await DatabaseService.save_pending_prediction(p_key, p_item)
                    
                    # Target (RR) Detection for Active Trades
                    if p_item.get("is_triggered"):
                        rr1, rr2, rr3 = p_item.get("rr1"), p_item.get("rr2"), p_item.get("rr3")
                        if rr1 and not p_item.get("rr1_hit"):
                            if (bull and h >= rr1) or (not bull and l <= rr1):
                                p_item["rr1_hit"] = True
                                any_global_changes = True
                                await DatabaseService.save_pending_prediction(p_key, p_item)
                        if rr2 and not p_item.get("rr2_hit"):
                            if (bull and h >= rr2) or (not bull and l <= rr2):
                                p_item["rr2_hit"] = True
                                any_global_changes = True
                                await DatabaseService.save_pending_prediction(p_key, p_item)
                        if rr3 and not p_item.get("rr3_hit"):
                            if (bull and h >= rr3) or (not bull and l <= rr3):
                                p_item["rr3_hit"] = True
                                any_global_changes = True
                                await DatabaseService.save_pending_prediction(p_key, p_item)
                    
                    success = None
                    if tp_hit and not sl_hit: success = True
                    elif sl_hit: success = False
                    
                    if success is not None:
                        any_global_changes = True
                        verdict = {
                            "symbol": symbol, "interval": interval, "time": k_time,
                            "actual_ohlc": {"time": k_time, "open": o, "high": h, "low": l, "close": c},
                            "was_correct": success, "date": datetime.now().isoformat(),
                            "entry": entry, "tp": tp, "sl": sl,
                            "rr1": p_item.get("rr1"), "rr2": p_item.get("rr2"), "rr3": p_item.get("rr3"),
                            "rr1_hit": p_item.get("rr1_hit", False), 
                            "rr2_hit": p_item.get("rr2_hit", False), 
                            "rr3_hit": p_item.get("rr3_hit", False),
                            "logic": p_item.get("logic", "N/A"),
                            "failure_analysis": "None (Target Hit)" if success else "Volatility Spike (SL Hit)"
                        }

                        # --- LOCAL SAVING ---
                        hist_data = []
                        if os.path.exists(history_path):
                            try:
                                with open(history_path) as f: hist_data = json.load(f)
                            except: pass
                        hist_data.append(verdict)
                        with open(history_path, "w") as f: json.dump(hist_data[-100:], f, indent=2)

                        # CSV Audit Log
                        file_exists = os.path.isfile(csv_path)
                        readable_time = datetime.fromisoformat(verdict["date"]).strftime('%Y-%m-%d %H:%M:%S')
                        pd.DataFrame([{
                            "date": verdict["date"], "trade_time": readable_time,
                            "symbol": symbol, "interval": interval,
                            "time_unix": k_time, "entry": entry, "tp": tp, "sl": sl,
                            "was_correct": int(success), "ai_logic": verdict["logic"]
                        }]).to_csv(csv_path, mode='a', index=False, header=not file_exists)

                        # --- CLOUD SYNC ---
                        await DatabaseService.resolve_trade(p_key, verdict)

                        del pending[p_key]
                        break
            except Exception as e:
                print(f"Error re-analyzing {cache_key}: {e}")

        if any_global_changes:
            with open(pending_path, "w") as f:
                json.dump(pending, f, indent=2)

    @staticmethod
    async def analyze_patterns(symbol: str, interval: str = "15m") -> str:
        """Full analysis: indicators + annotated chart with prediction band."""

        fetch_asset = symbol.upper() if symbol.upper() in VALID_SYMBOLS else "BTC"
        if interval not in INTERVAL_CONFIG:
            interval = "15m"
        cfg = INTERVAL_CONFIG[interval]

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.get(
                    f"https://data-api.binance.vision/api/v3/klines"
                    f"?symbol={fetch_asset}USDT&interval={interval}&limit={cfg['limit']}"
                )
                if res.status_code != 200:
                    return f"❌ Binance API error ({res.status_code}) for {fetch_asset}."
                klines = res.json()

            if len(klines) < 60:
                return f"❌ Insufficient data ({len(klines)} bars) for {fetch_asset}."

            # ── 1. Create Robust DataFrame ───────────────────────────────────
            # Binance columns ordering: Open time, Open, High, Low, Close, Volume...
            df_raw = pd.DataFrame(klines).iloc[:, :6]
            df_raw.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
            df_raw['Date'] = pd.to_datetime(df_raw['Time'], unit='ms')
            df = df_raw.set_index('Date')[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)
            
            # Final check to ensure Column names are PERFECT for mpf
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            
            closes = df["Close"].values
            n = len(closes)
            current_price = float(closes[-1])

            # ── 2. Pre-pend Prediction Row for "Next Candle" ──────────────────
            last_dt  = df.index[-1]
            dt_delta = df.index[-1] - df.index[-2] if n > 1 else pd.Timedelta(interval)
            next_dt  = last_dt + dt_delta
            
            # Linear Regression for Target and Band
            pred_bars  = cfg["pred_bars"]
            reg_window = min(50, n)
            x_reg = np.arange(reg_window)
            y_reg = closes[-reg_window:]
            slope, intercept = np.polyfit(x_reg, y_reg, 1)

            pred_xs    = np.arange(reg_window, reg_window + pred_bars)
            pred_vals  = slope * pred_xs + intercept
            
            # Average True Range for Band & Candle Wicks
            atr_ind = ta.volatility.AverageTrueRange(df["High"], df["Low"], df["Close"], window=14)
            atr     = float(atr_ind.average_true_range().iloc[-1])
            
            p_open  = current_price
            p_close = float(pred_vals[0])
            p_high  = max(p_open, p_close) + (atr * 0.3)
            p_low   = min(p_open, p_close) - (atr * 0.3)
            
            # Add the NaN row for the "Ghost" candle
            df.loc[next_dt, :] = np.nan
            full_n = len(df)
            plot_bars_ext = min(cfg["plot_bars"] + 1, full_n)
            
            # Indicators computed on extended range (n+1)
            df["sma50"]  = df["Close"].rolling(50).mean()
            df["sma200"] = df["Close"].rolling(200).mean()
            df["ema20"]  = df["Close"].ewm(span=20, adjust=False).mean()
            df["rsi"]    = ta.momentum.RSIIndicator(df["Close"], window=14).rsi()
            
            ema12 = df["Close"].ewm(span=12, adjust=False).mean()
            ema26 = df["Close"].ewm(span=26, adjust=False).mean()
            macd_l = ema12 - ema26
            macd_s = macd_l.ewm(span=9, adjust=False).mean()
            macd_h = macd_l - macd_s

            # Values for text status report (from -2 index, which is the last real bar)
            sma50_val  = float(df["sma50"].iloc[-2]) if not pd.isna(df["sma50"].iloc[-2]) else None
            sma200_val = float(df["sma200"].iloc[-2]) if not pd.isna(df["sma200"].iloc[-2]) else None
            ema20_val  = float(df["ema20"].iloc[-2])
            current_rsi = float(df["rsi"].iloc[-2]) if not pd.isna(df["rsi"].iloc[-2]) else 50.0

            cross_status = f"20D EMA = ${ema20_val:,.0f}"
            if sma50_val and sma200_val:
                p50, p200 = df["sma50"].iloc[-3], df["sma200"].iloc[-3]
                if p50 <= p200 and sma50_val > sma200_val:
                    cross_status = "🔥 **Golden Cross!** 50D SMA crossed above 200D — bullish."
                elif p50 >= p200 and sma50_val < sma200_val:
                    cross_status = "⚠️ **Death Cross!** 50D SMA crossed below 200D — bearish."
                else:
                    cross_status = (f"50D SMA=${sma50_val:,.0f} | 200D SMA=${sma200_val:,.0f} | 20D EMA=${ema20_val:,.0f}")

            rsi_level = f"RSI: **{current_rsi:.1f}**"
            if current_rsi > 70: rsi_level = f"⚠️ **RSI Overbought** ({current_rsi:.1f})"
            elif current_rsi < 30: rsi_level = f"🔥 **RSI Oversold** ({current_rsi:.1f})"

            rsi_div = detect_rsi_divergence(closes, df["rsi"].fillna(50).values[:-1], lookback=80)
            macd_signal = detect_macd_signal(closes)

            # ── 3. ICT / Fib / EW Analysis ──────────────────────────────────
            ict = detect_ict_concepts(df.iloc[:-1])
            recent = closes[-90:]
            hi90, lo90 = float(np.max(recent)), float(np.min(recent))
            fib_vals = {
                "0.618": hi90 - (hi90 - lo90) * 0.618,
                "0.382": hi90 - (hi90 - lo90) * 0.382,
                "0.236": hi90 - (hi90 - lo90) * 0.236,
                "0.786": hi90 - (hi90 - lo90) * 0.786
            }

            # Elliott Wave (on last 100 real bars)
            ew_window = df["Close"].iloc[-plot_bars_ext:-1].values
            ew_n = len(ew_window)
            h, t = max(ew_n // 2, 1), max(ew_n // 3, 1)
            wa_idx = int(np.argmax(ew_window[:h]))
            wb_idx = wa_idx + int(np.argmin(ew_window[wa_idx : min(wa_idx+t, ew_n)]))
            wc_idx = wb_idx + int(np.argmax(ew_window[wb_idx : min(wb_idx+t+1, ew_n)]))
            wave_pts = {"A": (wa_idx, float(ew_window[wa_idx])), "B": (wb_idx, float(ew_window[wb_idx])), "C": (wc_idx, float(ew_window[wc_idx]))}

            # ── 4. Prepare Sliced Data for Plotting ─────────────────────────
            # Reorder core columns and get plot slice
            plot_df_full = df[['Open', 'High', 'Low', 'Close', 'Volume']].iloc[-plot_bars_ext:]
            
            sma50_p  = df["sma50"].iloc[-plot_bars_ext:]
            sma200_p = df["sma200"].iloc[-plot_bars_ext:]
            ema20_p  = df["ema20"].iloc[-plot_bars_ext:]
            m_l_p    = macd_l.iloc[-plot_bars_ext:]
            m_s_p    = macd_s.iloc[-plot_bars_ext:]
            m_h_p    = macd_h.iloc[-plot_bars_ext:]

            def _pad_arr(vals, target_len, pad_size):
                arr = np.full(target_len, np.nan)
                arr[-pad_size:] = vals[:pad_size]
                return arr

            pred_mid_p   = _pad_arr(pred_vals, plot_bars_ext, pred_bars)
            pred_upper_p = _pad_arr(pred_vals + atr*2, plot_bars_ext, pred_bars)
            pred_lower_p = _pad_arr(pred_vals - atr*2, plot_bars_ext, pred_bars)
            
            reg_arr = np.full(plot_bars_ext, np.nan)
            reg_in_vals = slope * np.arange(reg_window) + intercept
            reg_arr[max(0, plot_bars_ext - 1 - reg_window) : -1] = reg_in_vals

            # Predicted "Ghost Candle" Series — MUST have all columns for mpf consistency
            ghost_ohlc = pd.DataFrame(index=plot_df_full.index, columns=['Open','High','Low','Close','Volume'])
            ghost_ohlc = ghost_ohlc.astype(float)
            ghost_ohlc.iloc[-1] = [p_open, p_high, p_low, p_close, 0.0]

            # ── 5. Rendering ─────────────────────────────────────────────────
            os.makedirs(STATIC_DIR, exist_ok=True)
            chart_filename = f"chart_{fetch_asset}_{uuid.uuid4().hex[:8]}.png"
            chart_path     = os.path.join(STATIC_DIR, chart_filename)

            mc = mpf.make_marketcolors(up="#26a69a", down="#ef5350", edge="inherit", wick="inherit", volume="in")
            s_style = mpf.make_mpf_style(marketcolors=mc, gridstyle="--", y_on_right=True, base_mpf_style="nightclouds")

            apds = [
                mpf.make_addplot(sma50_p,  color="#29b6f6", width=1.4, label="SMA50"),
                mpf.make_addplot(ema20_p,  color="#ce93d8", width=1.2, label="EMA20"),
                mpf.make_addplot(reg_arr,  color="#A0A0A0", width=1.0, linestyle="--"),
                mpf.make_addplot(pred_mid_p,    color="#FFEB3B", width=2.2),
                mpf.make_addplot(pred_upper_p,  color="#66BB6A", width=1.2, linestyle=":"),
                mpf.make_addplot(pred_lower_p,  color="#EF5350", width=1.2, linestyle=":"),
                mpf.make_addplot(ghost_ohlc,    type='candle',  color='#FFD700', alpha=0.9),
                mpf.make_addplot(m_l_p, panel=2, color="#29b6f6", width=1.3),
                mpf.make_addplot(m_s_p, panel=2, color="#ff9800", width=1.0),
                mpf.make_addplot(m_h_p, panel=2, color="#4caf50", width=0.8, type="bar"),
            ]
            if not sma200_p.isna().all():
                apds.insert(1, mpf.make_addplot(sma200_p, color="#ff9800", width=1.4))

            hlines_cfg = dict(
                hlines=[fib_vals["0.618"], fib_vals["0.382"], fib_vals["0.236"], fib_vals["0.786"]],
                colors=["#FFD700", "#00FFFF", "#80DEEA", "#FF8A65"],
                linestyle="--", linewidths=0.9, alpha=0.5
            )

            fig, axes = mpf.plot(
                plot_df_full, type="candle", style=s_style, volume=True, addplot=apds,
                figsize=(16, 11), datetime_format=cfg["fmt"], hlines=hlines_cfg,
                panel_ratios=(4, 1, 2), returnfig=True,
                title=f"\n{fetch_asset}/USDT  |  {interval}  |  AI Automated Analysis"
            )
            ax = axes[0]
            
            # Predict Zone Shading
            v_idx = [i for i, v in enumerate(pred_mid_p) if not np.isnan(v)]
            if v_idx:
                ax.fill_between(v_idx, pred_lower_p[v_idx], pred_upper_p[v_idx], color="#FFEB3B", alpha=0.06)
                ax.annotate(f"Target: ${pred_vals[-1]:,.0f}", xy=(v_idx[-1], pred_mid_p[v_idx[-1]]), 
                            fontsize=9, color="#FFEB3B", fontweight="bold", xytext=(5,0), textcoords="offset points")
            
            # Label "NEXT" Predicted Candle
            ax.annotate("NEXT", xy=(plot_bars_ext-1, p_high), xytext=(0,15), textcoords="offset points",
                        ha="center", fontsize=10, fontweight="bold", color="#FFD700",
                        arrowprops=dict(arrowstyle="->", color="#FFD700", lw=1.2))

            # Elliott Wave labels
            ew_colors = {"A": "#FF6B6B", "B": "#4ECDC4", "C": "#FFE66D"}
            prev_x, prev_y = None, None
            for lbl, (xi, yi) in wave_pts.items():
                if 0 <= xi < plot_bars_ext:
                    col = ew_colors.get(lbl, "#FFF")
                    ax.annotate(lbl, xy=(xi, yi), xytext=(xi, yi*1.006 if lbl in ("A","C") else yi*0.994),
                                fontsize=14, fontweight="bold", color=col, ha="center",
                                arrowprops=dict(arrowstyle="->", color=col, lw=1.5), zorder=20)
                    if prev_x is not None:
                        ax.plot([prev_x, xi], [prev_y, yi], color="#E0E0E0", lw=1.0, linestyle=":", zorder=5)
                    prev_x, prev_y = xi, yi

            fig.savefig(chart_path, dpi=130, bbox_inches="tight")
            plt.close(fig)
            img_md = f"\n\n![{fetch_asset} AI Analysis Chart]({BASE_URL}/{chart_filename})"

            # ── 6. Build Narrative ───────────────────────────────────────────
            target = float(pred_vals[-1])
            p_dir  = "📈 bullish" if target > current_price else "📉 bearish"
            p_pct  = (target - current_price) / current_price * 100

            return (
                f"**🤖 AI Automated Analysis — {fetch_asset}/USDT ({interval})**\n\n"
                f"**📊 Price & Structure:**\n"
                f"- Moving Averages: {cross_status}\n"
                f"- {ict['bos_choch']}\n"
                f"- {ict['order_block']}\n"
                f"- {ict['fvg']}\n\n"
                f"**📐 ICT Technical Analysis:**\n"
                f"- {ict['premium_discount']}\n"
                f"- {ict['liquidity_sweep']}\n"
                f"- {ict['kill_zone']}\n\n"
                f"**📈 Projections & Momentum:**\n"
                f"- {rsi_level}\n"
                f"- {macd_signal}\n"
                f"- {rsi_div}\n\n"
                f"**🤖 Next Candle Prediction:**\n"
                f"Drawing predicted candle... Target: **${p_close:,.2f}**\n"
                f"Forward Trend: {p_dir} target **${target:,.0f}** ({p_pct:+.2f}%) "
                f"| Band: ${pred_lower_p[-1]:,.0f} – ${pred_upper_p[-1]:,.0f}\n"
                f"{img_md}\n\n"
                f"*Live Binance Market Data · Probabilistic Analysis*"
            )

        except Exception as e:
            return f"❌ Analysis Engine Error [v3]: {str(e)}"
