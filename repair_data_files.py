import json
import os

def repair_json_file(path):
    if not os.path.exists(path):
        print(f"File {path} does not exist. Skipping.")
        return

    print(f"Checking {path}...")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read().strip()
        
        if not data:
            print(f"{path} is empty. Resetting to default.")
            with open(path, 'w', encoding='utf-8') as f:
                f.write("[]" if "history" in path else "{}")
            return

        try:
            json.loads(data)
            print(f"{path} is already valid.")
        except json.JSONDecodeError:
            print(f"{path} is INVALID. Attempting repair...")
            # Simple approach: truncate from end until it works or we hit a safe spot
            lines = data.splitlines()
            repaired = False
            for i in range(len(lines), 0, -1):
                test_str = "\n".join(lines[:i]).strip()
                if not test_str: continue
                
                # Close potential brackets
                for closure in ["", "}", "]", "}]", "}}", "]", "}"]:
                    try:
                        candidate = test_str + closure
                        json.loads(candidate)
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(candidate)
                        print(f"Successfully repaired {path} at line {i}.")
                        repaired = True
                        break
                    except:
                        continue
                if repaired: break
            
            if not repaired:
                print(f"COULD NOT REPAIR {path}. Resetting.")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write("[]" if "history" in path else "{}")

    except Exception as e:
        print(f"Error processing {path}: {e}")

data_dir = r'd:\crypto\backend\data'
repair_json_file(os.path.join(data_dir, 'pending_predictions.json'))
repair_json_file(os.path.join(data_dir, 'prediction_history.json'))
