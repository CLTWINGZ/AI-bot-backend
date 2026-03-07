"""
Autopilot Engine
================
• Runs multi-horizon analysis (1m-chart, 1d/1w/1M forecast) automatically
  every N seconds and broadcasts updates to all connected WebSocket clients.
• Frontend subscribes to /api/ws/autopilot for live push notifications.
"""

import asyncio
import json
import time
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from .pattern_recognition import PatternBot
from .forecasting import ForecastingEngine

# ── Global connection registry ────────────────────────────────────────────────
_connections: Set[WebSocket] = set()
_last_payload: dict | None = None       # cache last result for new joiners
_task_running: bool = False

AUTOPILOT_INTERVAL_SECS = 60           # re-run analysis every 60 s
DEFAULT_ASSET = "BTC"

# ─────────────────────────────────────────────────────────────────────────────
async def register(ws: WebSocket):
    """Accept a new WebSocket and send the cached payload immediately."""
    await ws.accept()
    _connections.add(ws)
    if _last_payload:
        try:
            await ws.send_json(_last_payload)
        except Exception:
            pass

def unregister(ws: WebSocket):
    _connections.discard(ws)


async def _broadcast(payload: dict):
    """Push payload to every connected client; remove dead sockets."""
    global _last_payload
    _last_payload = payload
    dead = set()
    for ws in list(_connections):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    for ws in dead:
        _connections.discard(ws)


# ─────────────────────────────────────────────────────────────────────────────
async def _run_cycle(asset: str = DEFAULT_ASSET):
    """
    One complete autopilot cycle:
      1. 1m PatternBot analysis (fast intraday)
      2. Multi-horizon forecast (1d / 1w / 1m)
    """
    results = {"type": "autopilot", "asset": asset,
               "timestamp": time.time(), "error": None}

    try:
        # ── 1-minute chart analysis ───────────────────────────────────────
        pred_data = await PatternBot.get_ohlc_prediction(asset, interval="1m", persist=False)
        p = pred_data.get("prediction", {})
        conf = p.get("confidence", "N/A")
        logic = p.get("logic", "Scanning...")
        
        pattern_text = f"- **AI Conviction:** {conf}\\n"
        for note in logic.split(" | "):
            pattern_text += f"- {note}\\n"
            
        results["pattern_1m"] = pattern_text[:1200]

        # ── Multi-horizon forecasts ───────────────────────────────────────
        forecasts = {}
        for horizon_key in ["1d", "1w", "1m"]:
            fc = await ForecastingEngine.get_probabilistic_forecast(asset, horizon_key)
            forecasts[horizon_key] = fc["metadata"]
        results["forecasts"] = forecasts

    except Exception as e:
        results["error"] = str(e)

    return results


# ─────────────────────────────────────────────────────────────────────────────
async def autopilot_loop(asset: str = DEFAULT_ASSET):
    """
    Long-running background loop. Start once on app startup via asyncio.create_task().
    Skips a cycle gracefully if no clients are connected (saves API calls).
    """
    global _task_running
    _task_running = True
    
    # Start the faster re-analysis loop as a sub-task
    asyncio.create_task(re_analysis_tracker())
    
    while True:
        if _connections:          # only compute when someone's watching
            payload = await _run_cycle(asset)
            await _broadcast(payload)
        await asyncio.sleep(AUTOPILOT_INTERVAL_SECS)

async def re_analysis_tracker():
    """
    Runs every 10 seconds to check all pending trades against latest price action.
    Broadcasting stats ensures "Live" updates on the frontend.
    """
    from .stats_service import StatsService
    while True:
        if _connections:
            try:
                # 1. Run the global re-analysis engine in PatternBot
                await PatternBot.re_analyze_all_pending()
                
                # 2. Fetch updated stats and broadcast
                stats = StatsService.get_prediction_stats()
                await _broadcast({
                    "type": "autopilot_stats",
                    "timestamp": time.time(),
                    "stats": stats
                })
            except Exception as e:
                print(f"Autopilot Re-Analysis Error: {e}")
        await asyncio.sleep(10) # 10s intervals for live feel


# ─────────────────────────────────────────────────────────────────────────────
async def handle_ws(websocket: WebSocket):
    """
    WebSocket handler for /api/ws/autopilot.
    Accepts connection, registers it, waits for client to disconnect.
    """
    await register(websocket)
    try:
        # Trigger an immediate first cycle for this client
        payload = await _run_cycle()
        await _broadcast(payload)
        # Keep connection alive — client only needs to listen
        while True:
            await asyncio.sleep(5)
            try:
                # Ping to detect disconnects
                await websocket.send_json({"type": "ping"})
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        unregister(websocket)
