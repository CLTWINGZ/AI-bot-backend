import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from supabase import create_client, Client

# --- Configuration (Set these in your .env or Render/Vercel settings) ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

class DatabaseService:
    _instance: Optional[Client] = None
    _lock = asyncio.Lock()

    @classmethod
    def get_client(cls) -> Optional[Client]:
        """Lazy initialization of the Supabase client."""
        if not cls._instance and SUPABASE_URL and SUPABASE_KEY:
            try:
                cls._instance = create_client(SUPABASE_URL, SUPABASE_KEY)
            except Exception as e:
                print(f"DATABASE_SERVICE ERROR: Failed to init Supabase - {e}")
        return cls._instance

    @classmethod
    async def save_pending_prediction(cls, p_key: str, p_item: Dict[str, Any]):
        """Dual-Persists: Cloud DB + Local File."""
        # 1. Always save locally first (Shadow Backup) with Lock
        async with cls._lock:
            cls._local_save_pending(p_key, p_item)

        # 2. Save to Cloud if configured
        client = DatabaseService.get_client()
        if client:
            try:
                data = {
                    "id": p_key,
                    "symbol": p_item["symbol"],
                    "interval": p_item["interval"],
                    "timestamp": p_item["timestamp"],
                    "entry": float(p_item["entry"]),
                    "tp": float(p_item["tp"]),
                    "sl": float(p_item["sl"]),
                    "bull": bool(p_item["bull"]),
                    "is_triggered": bool(p_item.get("is_triggered", False)),
                    "logic": p_item.get("logic", ""),
                    "prediction_json": json.dumps(p_item.get("prediction", {})),
                    "rr1_hit": bool(p_item.get("rr1_hit", False)),
                    "rr2_hit": bool(p_item.get("rr2_hit", False)),
                    "rr3_hit": bool(p_item.get("rr3_hit", False)),
                    "created_at": "now()"
                }
                client.table("pending_predictions").upsert(data).execute()
            except Exception as e:
                print(f"CLOUD DB ERROR (Pending): {e}")

    @staticmethod
    def get_all_pending() -> Dict[str, Dict[str, Any]]:
        """Retrieves active signals (Prioritizes Cloud DB)."""
        client = DatabaseService.get_client()
        if client:
            try:
                res = client.table("pending_predictions").select("*").execute()
                if res.data:
                    pending = {}
                    for row in res.data:
                        row["prediction"] = json.loads(row["prediction_json"])
                        pending[row["id"]] = row
                    return pending
            except Exception:
                pass
        
        # Fallback to local if cloud fails or not configured
        return DatabaseService._local_get_pending()

    @classmethod
    async def resolve_trade(cls, p_key: str, verdict: Dict[str, Any]):
        """Dual-Resolve: Cloud DB + Local History."""
        # 1. Always process locally (Shadow Backup) with Lock
        async with cls._lock:
            cls._local_resolve_trade(p_key, verdict)

        # 2. Process in Cloud if configured
        client = DatabaseService.get_client()
        if client:
            try:
                history_data = {
                    "symbol": verdict["symbol"],
                    "interval": verdict["interval"],
                    "time_unix": verdict["time"],
                    "date": verdict["date"],
                    "entry": float(verdict["entry"]),
                    "tp": float(verdict["tp"]),
                    "sl": float(verdict["sl"]),
                    "was_correct": bool(verdict["was_correct"]),
                    "logic": verdict.get("logic", ""),
                    "actual_ohlc": json.dumps(verdict.get("actual_ohlc", {})),
                    "failure_analysis": verdict.get("failure_analysis", "None")
                }
                client.table("prediction_history").insert(history_data).execute()
                client.table("pending_predictions").delete().eq("id", p_key).execute()
            except Exception as e:
                print(f"CLOUD DB ERROR (Resolve): {e}")

    @staticmethod
    def get_history(limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch permanent history for charts and stats."""
        client = DatabaseService.get_client()
        if not client:
            return DatabaseService._local_get_history(limit)

        try:
            res = client.table("prediction_history").select("*").order("date", desc=True).limit(limit).execute()
            for row in res.data:
                if row.get("actual_ohlc"):
                    row["actual_ohlc"] = json.loads(row["actual_ohlc"])
            return res.data
        except Exception as e:
            print(f"DATABASE_SERVICE ERROR: Failed to fetch history - {e}")
            return []

    # --- Local Fallbacks (Restores original CSV/JSON logic) ---
    @staticmethod
    def _local_save_pending(p_key, p_item):
        """Restores logic with standardized path."""
        import pandas as pd
        local_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        os.makedirs(local_dir, exist_ok=True)
        path_j = os.path.join(local_dir, "pending_predictions.json")
        path_c = os.path.join(local_dir, "prediction_history.csv")
        
        # 1. Update JSON
        data = {}
        if os.path.exists(path_j):
            try:
                with open(path_j) as f: data = json.load(f)
            except: pass
        data[p_key] = p_item
        with open(path_j, "w") as f: json.dump(data, f, indent=2)

        # 2. Record Filtered/Qualified in CSV for AI Memory (Shadow Log)
        if "prediction" in p_item:
            try:
                readable_time = datetime.fromisoformat(p_item["timestamp"]).strftime('%Y-%m-%d %H:%M:%S')
                pd.DataFrame([{
                    "date": p_item["timestamp"],
                    "trade_time": readable_time,
                    "symbol": p_item["symbol"],
                    "interval": p_item["interval"],
                    "time_unix": p_item["prediction"]["time"],
                    "entry": p_item.get("entry", 0), "tp": p_item.get("tp", 0), "sl": p_item.get("sl", 0),
                    "was_correct": -1, # Pending/Filtered
                    "ai_logic": p_item.get("logic", "")
                }]).to_csv(path_c, mode='a', index=False, header=not os.path.isfile(path_c))
            except: pass

    @staticmethod
    def _local_get_pending():
        local_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        path = os.path.join(local_dir, "pending_predictions.json")
        if os.path.exists(path):
            try:
                with open(path) as f: return json.load(f)
            except: return {}
        return {}

    @staticmethod
    def _local_resolve_trade(p_key, verdict):
        """Restores logic for resolving trades with standardized paths."""
        import pandas as pd
        local_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        os.makedirs(local_dir, exist_ok=True)
        path_h = os.path.join(local_dir, "prediction_history.json")
        path_c = os.path.join(local_dir, "prediction_history.csv")
        path_p = os.path.join(local_dir, "pending_predictions.json")
        
        # 1. Update JSON History
        hist = []
        if os.path.exists(path_h):
            try:
                with open(path_h) as f: hist = json.load(f)
            except: pass
        hist.append(verdict)
        with open(path_h, "w") as f: json.dump(hist[-100:], f, indent=2)

        # 2. Update CSV Audit
        try:
            readable_time = datetime.fromisoformat(verdict["date"]).strftime('%Y-%m-%d %H:%M:%S')
            pd.DataFrame([{
                "date": verdict["date"], "trade_time": readable_time,
                "symbol": verdict["symbol"], "interval": verdict["interval"],
                "time_unix": verdict["time"], "entry": verdict["entry"], 
                "tp": verdict["tp"], "sl": verdict["sl"],
                "was_correct": int(verdict["was_correct"]), 
                "ai_logic": verdict.get("logic", "N/A")
            }]).to_csv(path_c, mode='a', index=False, header=not os.path.isfile(path_c))
        except: pass

        # 3. Remove from pending JSON
        pending = DatabaseService._local_get_pending()
        if p_key in pending:
            print(f"DEBUG: Removing {p_key} from local pending JSON.")
            del pending[p_key]
        with open(path_p, "w") as f: json.dump(pending, f, indent=2)

    @staticmethod
    def _local_get_history(limit):
        local_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        path = os.path.join(local_dir, "prediction_history.json")
        if os.path.exists(path):
            try:
                with open(path) as f: 
                    data = json.load(f)
                    return data[-limit:]
            except: return []
        return []
