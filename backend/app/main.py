import os
import json
import asyncio
from typing import Optional
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# ── API Router Import ────────────────────────────────────────────────────────
from app.api.endpoints import router as api_router
from app.services import autopilot

app = FastAPI(title="CryptoInsight Alpha API", version="2.5.0")

# ── Robust CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Exception Handler ───────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"CRITICAL ERROR: {exc}")
    return JSONResponse(
        status_code=500,
        content={"message": f"Server Error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true"
        }
    )

# ── API Routes ─────────────────────────────────────────────────────────────
# IMPORTANT: Mounting the router directly so /api/settings, /api/ws/chat etc work
app.include_router(api_router, prefix="/api")

@app.get("/api/beacon")
def beacon():
    return {"status": "found", "version": "v2.5.1-STABLE"}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "CryptoInsight Alpha API v2.5 - FULLY FUNCTIONAL"}

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Autopilot background loop ───────────────────────────────────────────────
@app.on_event("startup")
async def start_autopilot():
    print("DEBUG: Loading API configuration from persistence...")
    from app.api.endpoints import _read_env
    env = _read_env()
    for k in ["GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_API_BASE", "LLM_MODEL"]:
        if env.get(k):
            os.environ[k] = env[k]

    print("DEBUG: Starting Autopilot background loop...")
    asyncio.create_task(autopilot.autopilot_loop("BTC"))

    print("DEBUG: Starting GitHub Auto-Sync background loop...")
    from app.services import github_sync
    asyncio.create_task(github_sync.sync_csv_to_github())
