import numpy as np

def get_pivots(highs, lows, window=3):
    """
    Identifies local swing highs and swing lows.
    A pivot is the highest/lowest point in its local window.
    """
    pivots_high = []
    pivots_low = []
    
    for i in range(window, len(highs) - window):
        # Is local peak? (Highest in [i-window, i+window])
        if highs[i] == max(highs[i-window:i+window+1]):
            # Avoid duplicate pivots for plateaus
            if not pivots_high or pivots_high[-1][1] != highs[i]:
                pivots_high.append((i, highs[i]))
            
        # Is local trough? (Lowest in [i-window, i+window])
        if lows[i] == min(lows[i-window:i+window+1]):
             # Avoid duplicates
            if not pivots_low or pivots_low[-1][1] != lows[i]:
                pivots_low.append((i, lows[i]))
            
    return pivots_high, pivots_low

def detect_patterns(df):
    """
    Analyzes recent OHLC data for geometric chart patterns.
    Returns: List of detected pattern names and their directions.
    """
    if len(df) < 50:
        return []

    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    
    # 1. Get swing pivots (swing highs and lows)
    ph, pl = get_pivots(highs, lows, window=3)
    
    patterns = []
    
    # ─── 5. Bull Flag (Bullish Continuation) ───
    # Quick spike (pole) followed by tight channel
    # Flags don't necessarily need many pivots
    if len(closes) >= 30:
        prev_move = (closes[-5] - closes[-25]) / closes[-25]
        recent_move = (closes[-1] - closes[-5]) / closes[-5]
        # Spike up > 1%, then slightly down/sideways consolidation
        if prev_move > 0.01 and -0.004 < recent_move < 0.001:
            patterns.append({"name": "Bull Flag", "type": "bullish", "weight": 18})

    # ─── 6. Bear Flag (Bearish Continuation) ───
    if len(closes) >= 30:
        prev_move = (closes[-5] - closes[-25]) / closes[-25]
        recent_move = (closes[-1] - closes[-5]) / closes[-5]
        # Spike down < -1%, then slightly up/sideways
        if prev_move < -0.01 and -0.001 < recent_move < 0.004:
            patterns.append({"name": "Bear Flag", "type": "bearish", "weight": 18})

    # Needs at least 2 pivots for complex shapes
    if len(ph) < 2 or len(pl) < 2:
        return patterns

    # Get most recent 5 pivots
    last_ph = ph[-5:]
    last_pl = pl[-5:]

    # ─── 1. Head and Shoulders (Bearish) ───
    # Sequence: High1, High2 (Head), High3 where H2 > H1 and H2 > H3
    if len(last_ph) >= 3:
        h1 = last_ph[-3][1]
        h2 = last_ph[-2][1] # Head
        h3 = last_ph[-1][1]
        if h2 > h1 * 1.002 and h2 > h3 * 1.002 and abs(h1 - h3) < (h1 * 0.005):
            patterns.append({"name": "Head & Shoulders", "type": "bearish", "weight": 20})

    # ─── 2. Inverse Head and Shoulders (Bullish) ───
    if len(last_pl) >= 3:
        l1 = last_pl[-3][1]
        l2 = last_pl[-2][1] # Head
        l3 = last_pl[-1][1]
        if l2 < l1 * 0.998 and l2 < l3 * 0.998 and abs(l1 - l3) < (l1 * 0.005):
            patterns.append({"name": "Inv Head & Shoulders", "type": "bullish", "weight": 20})

    # ─── 3. Double Top (Bearish) ───
    if len(last_ph) >= 2:
        t1 = last_ph[-2][1]
        t2 = last_ph[-1][1]
        if abs(t1 - t2) < (t1 * 0.001):
            patterns.append({"name": "Double Top", "type": "bearish", "weight": 15})

    # ─── 4. Double Bottom (Bullish) ───
    if len(last_pl) >= 2:
        b1 = last_pl[-2][1]
        b2 = last_pl[-1][1]
        if abs(b1 - b2) < (b1 * 0.001):
            patterns.append({"name": "Double Bottom", "type": "bullish", "weight": 15})

    # ─── 5. Bull Flag (Bullish Continuation) ───
    # Quick spike (pole) followed by tight channel
    # Use last 20 bars for flags
    if len(closes) >= 20:
        prev_move = (closes[-5] - closes[-20]) / closes[-20]
        recent_move = (closes[-1] - closes[-5]) / closes[-5]
        # Spike up > 1%, then slightly down/sideways consolidation
        if prev_move > 0.01 and -0.003 < recent_move < 0.001:
            patterns.append({"name": "Bull Flag", "type": "bullish", "weight": 18})

    # ─── 6. Bear Flag (Bearish Continuation) ───
    if len(closes) >= 20:
        prev_move = (closes[-5] - closes[-20]) / closes[-20]
        recent_move = (closes[-1] - closes[-5]) / closes[-5]
        # Spike down < -1%, then slightly up/sideways
        if prev_move < -0.01 and -0.001 < recent_move < 0.003:
            patterns.append({"name": "Bear Flag", "type": "bearish", "weight": 18})

    # ─── 7. Triangle / Wedge ───
    if len(last_ph) >= 2 and len(last_pl) >= 2:
        ph_slope = (last_ph[-1][1] - last_ph[-2][1]) / (last_ph[-1][0] - last_ph[-2][0] + 0.001)
        pl_slope = (last_pl[-1][1] - last_pl[-2][1]) / (last_pl[-1][0] - last_pl[-2][0] + 0.001)
        
        # Symmetrical Triangle: ph sloping down, pl sloping up
        if ph_slope < -0.0001 and pl_slope > 0.0001:
            patterns.append({"name": "Symmetrical Triangle", "type": "neutral", "weight": 10})
        # Ascending Triangle: ph flat, pl sloping up
        elif abs(ph_slope) < 0.0001 and pl_slope > 0.0001:
            patterns.append({"name": "Ascending Triangle", "type": "bullish", "weight": 15})
        # Descending Triangle: pl flat, ph sloping down
        elif abs(pl_slope) < 0.0001 and ph_slope < -0.0001:
            patterns.append({"name": "Descending Triangle", "type": "bearish", "weight": 15})

    return patterns
