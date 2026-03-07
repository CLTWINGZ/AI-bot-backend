import os
from .database_service import DatabaseService

class StatsService:
    @staticmethod
    def get_prediction_stats():
        """Returns historical AI accuracy, past records, and active pending trades from Cloud DB."""
        
        # 1. Fetch from History
        raw_history = DatabaseService.get_history(limit=50)
        
        # FILTER: Only show "Perfect" signals (boolean was_correct and no Filtering logic)
        data = [
            x for x in raw_history 
            if x.get("was_correct") in [True, False] 
            and "Filtering" not in str(x.get("logic", ""))
            and "Sub-Optimal" not in str(x.get("logic", ""))
        ]
                
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
