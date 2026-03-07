import asyncio
import sys
import os

# Ensure we can import from backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

from app.services.pattern_recognition import PatternBot

async def test():
    bot = PatternBot()
    print("Testing Ultra-Accuracy Signal Engine on 15m intervals...")
    for asset in ['BTCUSDT', 'ETHUSDT']:
        try:
            res = await bot.get_ohlc_prediction(asset, '15m')
            pred = res.get('prediction', {})
            conf = pred.get('confidence', 'N/A')
            logic = pred.get('logic', 'N/A')
            print(f"\\n{asset} 15m:")
            print(f"Confidence: {conf}")
            # print without getting unicode errors on windows
            print(f"Logic: {logic.encode('ascii', errors='ignore').decode()}")
        except Exception as e:
            print(f"{asset} Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
