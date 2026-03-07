import json
import os

path = r'd:\crypto\backend\data\pending_predictions.json'
try:
    with open(path, 'r', encoding='utf-8') as f:
        data = f.read()
    
    print("Checking JSON validity...")
    try:
        json.loads(data)
        print("JSON is already valid.")
    except Exception as e:
        print(f"Invalid JSON: {e}")
        # Try to find the last valid entry by closing braces iteratively backwards
        lines = data.splitlines()
        repaired = False
        for i in range(len(lines), 0, -1):
            test_str = "\n".join(lines[:i])
            # Ensure it ends with a comma if we want to add a closing brace
            # but usually it ends abruptly. Let's try to add the closing braces.
            for closure in ["", "}", "} }", "}\n}", "]\n}"]:
                try:
                    candidate = test_str + closure
                    json.loads(candidate)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(candidate)
                    print(f"Successfully repaired JSON by truncating at line {i} and adding closure.")
                    repaired = True
                    break
                except:
                    continue
            if repaired: break
        
        if not repaired:
            print("COULD NOT REPAIR. Resetting to empty object.")
            with open(path, 'w', encoding='utf-8') as f:
                f.write("{}")

except Exception as e:
    print(f"Error: {e}")
