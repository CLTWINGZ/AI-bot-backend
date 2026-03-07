import json
import os

path = r"d:\crypto\backend\data\prediction_history.json"
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    print(f"Before dedup: {len(data)}")
    
    seen = set()
    deduped = []
    for row in data:
        key = f"{row.get('symbol')}_{row.get('time')}"
        if key not in seen:
            seen.add(key)
            deduped.append(row)
            
    print(f"After dedup: {len(deduped)}")
    with open(path, "w") as f:
        json.dump(deduped, f, indent=2)
else:
    print("No history file found.")
