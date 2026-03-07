import httpx
import asyncio
import csv
import os
from datetime import datetime

async def fetch_klines(symbol, interval="1d"):
    all_klines = []
    # Fetch 1000 records per request, starting from epoch 0 to get all data
    limit = 1000
    start_time = 0
    
    print(f"Fetching historical data for {symbol}...")
    async with httpx.AsyncClient() as client:
        while True:
            url = f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}&startTime={start_time}"
            
            try:
                response = await client.get(url, timeout=10.0)
                if response.status_code != 200:
                    print(f"Error fetching {symbol}: {response.text}")
                    break
                    
                data = response.json()
                
                if not data or not isinstance(data, list):
                    break
                    
                all_klines.extend(data)
                
                # Timestamp is in milliseconds
                latest_date = datetime.fromtimestamp(data[-1][0] / 1000).strftime('%Y-%m-%d')
                print(f"Fetched up to {latest_date} for {symbol}. Total records: {len(all_klines)}")
                
                if len(data) < limit:
                    break
                    
                # advance start_time to the next millisecond after the last recorded open time
                start_time = data[-1][0] + 1
                await asyncio.sleep(0.2) # Small delay to respect rate limits
                
            except Exception as e:
                print(f"Exception occurred while fetching {symbol}: {e}")
                break
            
    return all_klines

def save_to_csv(symbol, data):
    file_dir = os.path.join("d:\\crypto", "backend", "data")
    os.makedirs(file_dir, exist_ok=True)
    filename = os.path.join(file_dir, f"{symbol}_historical_1d.csv")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        # Standard Binance Kline headers
        writer.writerow([
            "Open Time", "Open", "High", "Low", "Close", "Volume", 
            "Close Time", "Quote Asset Volume", "Number of Trades", 
            "Taker Buy Base Asset Volume", "Taker Buy Quote Asset Volume", "Ignore",
            "Human_Date"
        ])
        for row in data:
            human_date = datetime.fromtimestamp(row[0] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            row.append(human_date)
            writer.writerow(row)
            
    print(f"Successfully saved {len(data)} daily candles for {symbol} to {filename}\n")

async def main():
    # Gathering data for BTC, ETH, and ETC (Ethereum Classic, just in case you meant ETC instead of ETH)
    symbols = ["BTCUSDT", "ETHUSDT", "ETCUSDT"]
    for sym in symbols:
        data = await fetch_klines(sym)
        if data:
            save_to_csv(sym, data)

if __name__ == "__main__":
    asyncio.run(main())
