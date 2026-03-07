import json
import os
import time

p_path = r"d:\crypto\backend\data\pending_predictions.json"
h_path = r"d:\crypto\backend\data\prediction_history.json"

# 1. Load History to know what is finished
history_keys = set()
if os.path.exists(h_path):
    with open(h_path) as f:
        h_data = json.load(f)
        for row in h_data:
            key = f"{row['symbol']}_{row['interval']}_{row['time']}"
            history_keys.add(key)

# 2. Filter Pending
if os.path.exists(p_path):
    with open(p_path) as f:
        pending = json.load(f)
    
    clean_pending = {}
    now = time.time()
    
    for k, v in pending.items():
        # Skip if already in history
        if k in history_keys:
            continue
            
        # Skip if older than 1 hour (probably stale or missed)
        pred_time = v.get("prediction", {}).get("time", 0)
        if (now - pred_time) > 3600:
            continue
            
        clean_pending[k] = v
        
    print(f"Purged {len(pending) - len(clean_pending)} stale entries.")
    print(f"Remaining active/pending: {len(clean_pending)}")
    
    with open(p_path, "w") as f:
        json.dump(clean_pending, f, indent=2)
else:
    print("No pending file found.")
