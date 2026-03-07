import sys
import os
import json
import asyncio
from datetime import datetime

# Add the current directory to path so it can find 'backend'
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.app.services.pattern_recognition import PatternBot

async def test_rr_logic():
    print("Testing 1:3 RR Gating Logic...")
    bot = PatternBot()
    
    # We'll mock the get_ohlc_prediction behavior by calling it and checking output
    # Since it fetches real data, we'll just check if the logic notes contain the RR info
    result = await bot.get_ohlc_prediction("BTCUSDT", "1m")
    
    pred = result.get("prediction")
    if pred:
        logic = pred.get("logic", "")
        confidence = pred.get("confidence", "0%")
        
        print(f"Confidence: {confidence}")
        print(f"Logic: {logic}")
        
        # Check if R:R is in logic
        if "RR Ratio" in logic:
            print("PASS: RR Ratio is displayed in logic.")
            # Extract RR value
            try:
                rr = float(logic.split("RR Ratio: ")[1].split(" ")[0])
                print(f"Detected RR: {rr}")
                if rr >= 3.0:
                    print("PASS: RR is >= 3.0 as required for active signals.")
                else:
                    print("ERROR: RR is < 3.0 but signal was not suppressed!")
            except Exception as e:
                print(f"Could not parse RR from logic: {e}")
        elif "Low R:R" in logic:
            print("PASS: Low RR setup was correctly filtered and labeled.")
        elif "Awaiting 99.99% Setup" in logic:
            print("PASS: Generic suppression active (Low conviction).")
        else:
            print("WARNING: Logic string did not contain expected RR info.")

if __name__ == "__main__":
    asyncio.run(test_rr_logic())
