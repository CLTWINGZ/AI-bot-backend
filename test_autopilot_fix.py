import asyncio
import os
import sys

# Add the backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.pattern_recognition import PatternBot

async def test_autopilot():
    print("Testing PatternBot.get_ohlc_prediction...")
    try:
        # Test with 1m BTC
        result = await PatternBot.get_ohlc_prediction("BTC", "1m", persist=True)
        if "error" in result:
            print(f"Error in result: {result['error']}")
        else:
            print(f"Success! Prediction confidence: {result.get('prediction', {}).get('confidence')}")
            print(f"Logic: {result.get('prediction', {}).get('logic')[:100]}...")
            
        print("\nTesting PatternBot.re_analyze_all_pending...")
        await PatternBot.re_analyze_all_pending()
        print("Re-analysis complete (check logs above).")
        
    except Exception as e:
        print(f"Exception during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_autopilot())
