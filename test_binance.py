import httpx
import asyncio

async def main():
    urls = [
        "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
        "https://data-api.binance.vision/api/v3/ticker/24hr?symbol=BTCUSDT",
        "https://api.binance.us/api/v3/ticker/24hr?symbol=BTCUSDT",
    ]
    async with httpx.AsyncClient() as client:
        for url in urls:
            try:
                res = await client.get(url, timeout=5)
                print(f"{url} -> {res.status_code}")
            except Exception as e:
                print(f"{url} -> Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
