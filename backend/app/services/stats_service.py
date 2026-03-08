import os
from .database_service import DatabaseService

class StatsService:
    @staticmethod
    @staticmethod
    def get_prediction_stats():
        """Returns historical AI accuracy, past records, and active pending trades from Cloud DB."""
        
        # 1. Fetch from History
        raw_history = DatabaseService.get_history(limit=50)
        
        data = []
        for x in raw_history:
            # Unify time field (Cloud uses time_unix, Local uses time)
            t_val = x.get("time") or x.get("time_unix") or 0
            
            # Unify logic filtering
            logic = str(x.get("logic", ""))
            if x.get("was_correct") in [True, False] and "Filtering" not in logic and "Sub-Optimal" not in logic:
                data.append({
                    "symbol": x.get("symbol", "BTC"),
                    "interval": x.get("interval", "1m"),
                    "time": t_val,
                    "date": x.get("date"),
                    "was_correct": x.get("was_correct"),
                    "entry": x.get("entry"),
                    "tp": x.get("tp"),
                    "sl": x.get("sl"),
                    "logic": logic,
                    "failure_analysis": x.get("failure_analysis")
                })
                
        # 2. Fetch Pending
        pending_data = DatabaseService.get_all_pending()
                
        active_count = 0
        for key, p_trade in pending_data.items():
            if not p_trade: continue
            
            p_logic = p_trade.get("logic", "")
            if "Filtering" in p_logic or "Sub-Optimal" in p_logic:
                continue

            active_count += 1
            pred = p_trade.get("prediction", {})
            t_val = p_trade.get("timestamp_unix") or pred.get("time") or 0
            
            data.append({
                "symbol": p_trade.get("symbol", "BTC"),
                "interval": p_trade.get("interval", "1m"),
                "time": t_val,
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
                "logic": p_logic,
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
