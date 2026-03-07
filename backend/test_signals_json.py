import asyncio
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))
from app.services.pattern_recognition import PatternBot

async def test():
    bot = PatternBot()
    results = {}
    for asset in ['BTCUSDT', 'ETHUSDT']:
        try:
            res = await bot.get_ohlc_prediction(asset, '15m')
            pred = res.get('prediction', {})
            results[asset] = {
                "conf": pred.get("confidence", "N/A"),
                "logic": pred.get("logic", "N/A")
            }
        except Exception as e:
            results[asset] = {"error": str(e)}

    with open("test_out.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(test())
