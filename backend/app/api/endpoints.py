from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from ..models.chat import ChatRequest, ChatResponse
import json
import os

router = APIRouter()

# ─── Lazy Imports for production stability ───
def get_orchestrator():
    from ..services.orchestrator import ChatOrchestrator
    return ChatOrchestrator

def get_autopilot_service():
    from ..services import autopilot
    return autopilot

def _read_env() -> dict:
    """Reads purely from current os.environ for deployment support."""
    return dict(os.environ)

def _write_env(env: dict):
    """Writes to os.environ for immediate persistence in RAM."""
    for k, v in env.items():
        os.environ[k] = str(v)

class SettingsPayload(BaseModel):
    gemini_api_key: str = ""
    openai_api_key: str = ""
    openai_api_base: str = ""
    llm_model: str = ""

@router.get("/health")
def health_check():
    return {"status": "healthy"}

@router.get("/health2")
def health_check2():
    return {"status": "healthy2"}

@router.get("/api/config")
def get_config():
    return {
        "status": "ready",
        "gemini_model": "gemini-1.5-flash",
    }

@router.post("/test-post")
async def test_post():
    return {"status": "ok", "message": "POST connectivity confirmed"}

@router.post("/settings")
async def save_settings(payload: SettingsPayload):
    try:
        # 1. Update In-Memory Environment for Immediate Effect
        if payload.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = payload.gemini_api_key.strip()
        if payload.openai_api_key:
            os.environ["OPENAI_API_KEY"] = payload.openai_api_key.strip()
        if payload.openai_api_base:
            os.environ["OPENAI_API_BASE"] = payload.openai_api_base.strip()
        if payload.llm_model:
            os.environ["LLM_MODEL"] = payload.llm_model.strip()

        # 2. Try Persistence (might fail on Render, which is okay as we have env variables)
        try:
            env = _read_env()
            if payload.gemini_api_key: env["GEMINI_API_KEY"] = payload.gemini_api_key.strip()
            if payload.openai_api_key: env["OPENAI_API_KEY"] = payload.openai_api_key.strip()
            _write_env(env)
        except:
            pass # Swallow persistence errors in production

        return {"status": "saved", "message": "API keys updated successfully!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─── Standard HTTP POST /chat ─────────────────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    orchestrator = get_orchestrator()
    return await orchestrator.process(request)

# ─── Live WebSocket /ws/chat ───────────────────────────────────────────────────
@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                user_message = data.get("message", "").strip()
            except Exception:
                user_message = raw.strip()

            if not user_message:
                continue

            await websocket.send_json({"token": "", "typing": True, "done": False})

            request = ChatRequest(message=user_message)
            orchestrator = get_orchestrator()
            response = await orchestrator.process(request)

            words = response.message.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                await websocket.send_json({
                    "token": chunk, "typing": False, "done": False,
                    "is_warning": response.is_warning,
                })

            await websocket.send_json({
                "token": "", "done": True,
                "intent": response.intent_detected,
                "is_warning": response.is_warning,
                "metadata": response.metadata or {},
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"token": f"[Engine: {e}]", "done": True, "is_warning": True})
        except Exception:
            pass


# ─── MACD Multi-Timeframe Backtest ────────────────────────────────────────────
@router.get("/backtest/macd")
@router.get("/backtest/macd/{asset}")
async def macd_backtest(asset: str = "BTC"):
    """
    Run MACD (12,26,9) crossover backtest across 6 timeframes (1m→1d)
    using ~500 bars of live Binance data per timeframe.
    Returns: markdown table + best timeframe recommendation.
    """
    from ..services.forecasting import run_macd_multi_backtest
    asset = asset.upper()
    if asset not in {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE"}:
        asset = "BTC"
    result = await run_macd_multi_backtest(asset)
    return {"asset": asset, "result": result}


# ─── Raw OHLC + Prediction ────────────────────────────────────────────────────
@router.get("/ohlc/{symbol}/{interval}")
async def get_ohlc_data(symbol: str = "BTC", interval: str = "15m"):
    """
    Returns historical OHLC + a 'Ghost Candle' prediction row for JS charting.
    """
    from ..services.pattern_recognition import PatternBot
    return await PatternBot.get_ohlc_prediction(symbol, interval, persist=True)


# ─── Autopilot WebSocket /ws/autopilot ────────────────────────────────────────
@router.websocket("/ws/autopilot")
async def websocket_autopilot(websocket: WebSocket):
    """
    Streams automated analysis every 60 s:
      - 1m PatternBot chart analysis
      - 1d / 1w / 1m probabilistic forecasts
    """
    autopilot_service = get_autopilot_service()
    await autopilot_service.handle_ws(websocket)


# ─── Prediction Performance Stats ─────────────────────────────────────────────
@router.get("/prediction-stats")
async def get_prediction_stats():
    """Returns historical AI accuracy, past records, and active pending trades."""
    from ..services.stats_service import StatsService
    return StatsService.get_prediction_stats()
