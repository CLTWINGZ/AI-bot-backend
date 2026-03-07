import json
import os
from datetime import datetime

class StatsService:
    @staticmethod
    def get_prediction_stats():
        """Returns historical AI accuracy, past records, and active pending trades."""
        base_dir = os.path.dirname(__file__)
        history_path = os.path.join(base_dir, "..", "..", "data", "prediction_history.json")
        pending_path = os.path.join(base_dir, "..", "..", "data", "pending_predictions.json")
        
        data = []
        try:
            if os.path.exists(history_path):
                with open(history_path) as f:
                    data = json.load(f)
        except Exception as e:
            print(f"Error loading prediction history: {e}")
                
        # Load and format pending trades
        pending_data = {}
        try:
            if os.path.exists(pending_path):
                with open(pending_path) as f:
                    pending_data = json.load(f)
        except Exception as e:
            print(f"Error loading pending predictions: {e}")
                
        active_count = 0
        for key, p_trade in pending_data.items():
            if not p_trade: continue # Skip empty
            active_count += 1
            # Format to match history verdict format
            pred = p_trade.get("prediction", {})
            data.append({
                "symbol": p_trade.get("symbol", "BTC"),
                "interval": p_trade.get("interval", "1m"),
                "time": pred.get("time", 0),
                "was_correct": None,
                "is_active": p_trade.get("is_triggered", False), 
                "entry": p_trade.get("entry"),
                "tp": p_trade.get("tp"),
                "sl": p_trade.get("sl"),
                "rr1": pred.get("rr1"),
                "rr2": pred.get("rr2"),
                "rr3": pred.get("rr3"),
                "rr1_hit": p_trade.get("rr1_hit", False),
                "rr2_hit": p_trade.get("rr2_hit", False),
                "rr3_hit": p_trade.get("rr3_hit", False),
                "failure_analysis": None
            })
        
        hits = sum(1 for x in data if x.get("was_correct") is True)
        misses = sum(1 for x in data if x.get("was_correct") is False)
        
        completed = hits + misses
        rate = (hits / completed * 100) if completed > 0 else 0
        
        return {
            "data": data,
            "summary": {
                "total": len(data),
                "hits": hits,
                "misses": misses,
                "pending": active_count,
                "accuracy": f"{rate:.1f}%"
            }
        }
