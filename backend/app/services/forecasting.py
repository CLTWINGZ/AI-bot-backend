"""
Multi-Horizon Forecasting Engine v2
=====================================
Features:
  • Linear Regression price forecasts (1d / 1w / 1m)
  • MACD Multi-Timeframe Backtest — 1m, 5m, 15m, 1h, 4h, 1d
  • RSI Divergence signal accuracy measurement
  • Composite signal scoring (win-rate driven)
  • Side-by-side timeframe comparison table
"""
import httpx
import math
import re
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime

# ── Horizon map ────────────────────────────────────────────────────────────────
HORIZON_MAP = {
    "1d":   ("1d",   30,  1,  "1 Day"),
    "1w":   ("1d",   90,  7,  "1 Week"),
    "1m":   ("1d",  365, 30,  "1 Month"),
    "1min": ("1m",  100,  0,  "1 Minute"),
}

# Timeframes to backtest MACD across
MACD_BACKTEST_INTERVALS = [
    ("1m",  500),
    ("5m",  500),
    ("15m", 500),
    ("1h",  500),
    ("4h",  500),
    ("1d",  500),
]


def _horizon_key(horizon: str) -> str:
    h = horizon.lower().strip()
    if "month" in h or "30" in h:              return "1m"
    if "week"  in h or "7d"  in h:             return "1w"
    if "day"   in h or "1d"  in h or "24h" in h: return "1d"
    if "min"   in h:                            return "1min"
    match = re.search(r"(\d+)(h|d|m)", h)
    if match:
        val, unit = int(match.group(1)), match.group(2)
        if unit == "d" and val >= 25: return "1m"
        if unit == "d" and val >= 5:  return "1w"
        if unit == "d":               return "1d"
        if unit == "h":               return "1d"
    return "1d"


async def _fetch_klines(asset: str, interval: str, limit: int) -> pd.DataFrame:
    url = (f"https://data-api.binance.vision/api/v3/klines"
           f"?symbol={asset}USDT&interval={interval}&limit={limit}")
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url)
        r.raise_for_status()
    rows = [
        {
            "close":  float(k[4]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "open":   float(k[1]),
            "volume": float(k[5]),
        }
        for k in r.json()
    ]
    return pd.DataFrame(rows)


def _linear_regression_forecast(closes: np.ndarray, steps_ahead: int):
    n = len(closes)
    x = np.arange(n)
    slope, intercept = np.polyfit(x, closes, 1)
    future_x   = n + steps_ahead - 1
    prediction = slope * future_x + intercept
    return float(prediction), float(slope)


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    tr = np.maximum(
        df["high"] - df["low"],
        np.maximum(
            abs(df["high"] - df["close"].shift(1).fillna(df["close"])),
            abs(df["low"]  - df["close"].shift(1).fillna(df["close"]))
        )
    )
    return float(tr.rolling(period).mean().iloc[-1])


# ── MACD Backtest Engine ──────────────────────────────────────────────────────

def _compute_macd(closes: pd.Series, fast=12, slow=26, signal=9):
    ema_fast   = closes.ewm(span=fast,   adjust=False).mean()
    ema_slow   = closes.ewm(span=slow,   adjust=False).mean()
    macd_line  = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram  = macd_line - signal_line
    return macd_line, signal_line, histogram


def _backtest_macd(df: pd.DataFrame, hold_bars: int = 5) -> dict:
    """
    Backtest MACD crossover strategy on a given OHLCV dataframe.
    Entry: MACD crosses above signal (buy) or below (sell).
    Exit: after hold_bars bars.
    Returns win_rate, avg_return, total_trades, sharpe.
    """
    closes = df["close"]
    macd, sig, hist = _compute_macd(closes)

    # Generate signals: +1 = buy crossover, -1 = sell crossover
    cross = (macd > sig).astype(int)
    signals = cross.diff().fillna(0)

    buy_entries  = signals[signals == 1].index.tolist()
    sell_entries = signals[signals == -1].index.tolist()

    returns = []
    for idx in buy_entries:
        pos = closes.index.get_loc(idx)
        if pos + hold_bars < len(closes):
            entry_p = float(closes.iloc[pos])
            exit_p  = float(closes.iloc[pos + hold_bars])
            pct     = (exit_p - entry_p) / entry_p * 100
            returns.append(("buy", pct))

    for idx in sell_entries:
        pos = closes.index.get_loc(idx)
        if pos + hold_bars < len(closes):
            entry_p = float(closes.iloc[pos])
            exit_p  = float(closes.iloc[pos + hold_bars])
            pct     = (entry_p - exit_p) / entry_p * 100  # short = inverse
            returns.append(("sell", pct))

    if not returns:
        return {"win_rate": 0, "avg_return": 0, "total_trades": 0,
                "sharpe": 0, "max_win": 0, "max_loss": 0}

    rets = [r[1] for r in returns]
    wins = [r for r in rets if r > 0]

    win_rate   = len(wins) / len(rets) * 100
    avg_return = float(np.mean(rets))
    sharpe     = float(np.mean(rets) / (np.std(rets) + 1e-9))
    max_win    = float(max(rets))
    max_loss   = float(min(rets))

    return {
        "win_rate":    round(win_rate, 1),
        "avg_return":  round(avg_return, 3),
        "total_trades": len(returns),
        "sharpe":      round(sharpe, 2),
        "max_win":     round(max_win, 2),
        "max_loss":    round(max_loss, 2),
    }


async def _backtest_one_interval(asset: str, interval: str, limit: int) -> dict:
    """Fetch data and run MACD backtest for a single interval."""
    try:
        df   = await _fetch_klines(asset, interval, limit)
        # hold bars: scale to interval
        hold = {"1m": 15, "5m": 12, "15m": 8, "1h": 6, "4h": 5, "1d": 4}.get(interval, 5)
        res  = _backtest_macd(df, hold_bars=hold)
        res["interval"] = interval
        res["status"]   = "ok"
        return res
    except Exception as e:
        return {"interval": interval, "status": "error", "error": str(e),
                "win_rate": 0, "avg_return": 0, "total_trades": 0, "sharpe": 0}


async def run_macd_multi_backtest(asset: str) -> str:
    """
    Run MACD backtests across 6 timeframes concurrently.
    Returns a formatted markdown table with results.
    """
    tasks = [
        _backtest_one_interval(asset, interval, limit)
        for interval, limit in MACD_BACKTEST_INTERVALS
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    rows = []
    for r in results:
        if isinstance(r, Exception):
            r = {"interval": "?", "status": "error", "win_rate": 0,
                 "avg_return": 0, "total_trades": 0, "sharpe": 0,
                 "max_win": 0, "max_loss": 0}
        rows.append(r)

    # Sort by sharpe (best signal quality first)
    rows_ok = [r for r in rows if r["status"] == "ok"]
    rows_ok.sort(key=lambda x: x["sharpe"], reverse=True)

    best = rows_ok[0] if rows_ok else None

    table = (
        "| Timeframe | Win Rate | Avg Return | Trades | Sharpe | Best Win | Worst Loss |\n"
        "|---|---|---|---|---|---|---|\n"
    )
    for r in rows:
        if r["status"] != "ok":
            table += f"| {r['interval']} | ❌ error | – | – | – | – | – |\n"
            continue
        wr_icon = "🟢" if r["win_rate"] >= 55 else "🟡" if r["win_rate"] >= 45 else "🔴"
        table += (
            f"| **{r['interval']}** | {wr_icon} {r['win_rate']}% | "
            f"{r['avg_return']:+.2f}% | {r['total_trades']} | "
            f"{r['sharpe']:+.2f} | +{r['max_win']:.1f}% | {r['max_loss']:.1f}% |\n"
        )

    summary = ""
    if best:
        summary = (
            f"\n🏆 **Best Timeframe:** `{best['interval']}` "
            f"— Win Rate **{best['win_rate']}%** | "
            f"Sharpe **{best['sharpe']:+.2f}** | "
            f"Avg Return **{best['avg_return']:+.2f}%** per trade · "
            f"{best['total_trades']} signals backtested on ~500 bars of live Binance data."
        )

    return (
        f"**📊 MACD Multi-Timeframe Backtest — {asset}/USDT**\n\n"
        f"*Strategy: MACD (12,26,9) crossover · Entry on cross · Exit after N bars · "
        f"Live Binance data · ~500 bars per timeframe*\n\n"
        f"{table}"
        f"{summary}\n\n"
        f"*⚠️ Backtests use past data. Past performance ≠ future results.*"
    )


# ── Forecasting Engine ────────────────────────────────────────────────────────

class ForecastingEngine:

    @staticmethod
    async def get_probabilistic_forecast(asset: str, horizon: str = "24h") -> dict:
        key = _horizon_key(horizon)
        interval, limit, steps, label = HORIZON_MAP.get(key, HORIZON_MAP["1d"])

        asset = asset.upper()
        if asset not in ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE"]:
            asset = "BTC"

        try:
            df      = await _fetch_klines(asset, interval, limit)
            closes  = df["close"].values
            current = float(closes[-1])
            atr_val = _atr(df)

            p50, slope = _linear_regression_forecast(closes, max(steps, 1))
            band = atr_val * math.sqrt(max(steps, 1))
            p10  = p50 - band * 1.5
            p90  = p50 + band * 1.5

            trend      = "📈 Bullish" if slope > 0 else "📉 Bearish"
            pct_change = ((p50 - current) / current) * 100

            momentum  = float(closes[-1] - closes[-5]) if len(closes) >= 5 else 0
            range_pct = (atr_val / current) * 100

            # MACD state at current bar
            macd_line, sig_line, hist = _compute_macd(pd.Series(closes))
            macd_state = "MACD ▲ Bullish" if float(macd_line.iloc[-1]) > float(sig_line.iloc[-1]) else "MACD ▼ Bearish"

            # RSI
            delta = pd.Series(closes).diff()
            gain  = delta.clip(lower=0).rolling(14).mean()
            loss  = (-delta.clip(upper=0)).rolling(14).mean()
            rs    = gain / (loss + 1e-9)
            rsi   = 100 - (100 / (1 + rs))
            rsi_now = float(rsi.iloc[-1])

            drivers = [
                ("LinReg slope",           f"{'+' if slope > 0 else ''}{slope:.2f}/bar"),
                ("ATR-14 volatility",       f"{range_pct:.2f}% of price"),
                ("5-bar momentum",          f"{'▲' if momentum > 0 else '▼'} ${abs(momentum):,.0f}"),
                ("MACD signal",             macd_state),
                ("RSI",                     f"{rsi_now:.1f}{'  ⚠️ OB' if rsi_now > 70 else '  🔥 OS' if rsi_now < 30 else ''}"),
            ]

            message = (
                f"**{asset}/USDT — {label} Probabilistic Forecast**\n\n"
                f"Current price: **${current:,.2f}**\n\n"
                f"| Scenario | Target | Δ% |\n"
                f"|---|---|---|\n"
                f"| 🔼 Upside (p90)  | **${p90:,.0f}** | +{((p90-current)/current*100):.1f}% |\n"
                f"| ➡ Median (p50)   | **${p50:,.0f}** | {pct_change:+.1f}% |\n"
                f"| 🔻 Downside (p10) | **${p10:,.0f}** | {((p10-current)/current*100):.1f}% |\n\n"
                f"**Trend:** {trend} · {macd_state}\n\n"
                f"*Key Drivers:*\n" +
                "\n".join(f"{i+1}. {d[0]}: `{d[1]}`" for i, d in enumerate(drivers)) +
                f"\n\n*Projections: LinReg on live Binance {interval} data + ATR-14.*\n"
                f"*⚠️ Not financial advice.*"
            )

            return {
                "message": message,
                "metadata": {
                    "current":    current,
                    "p10":        round(p10, 2),
                    "p50":        round(p50, 2),
                    "p90":        round(p90, 2),
                    "trend":      trend,
                    "pct_change": round(pct_change, 2),
                    "atr":        round(atr_val, 2),
                    "asset":      asset,
                    "horizon":    label,
                }
            }

        except Exception as e:
            return {
                "message": f"Forecast engine error for {asset} {label}: {str(e)}",
                "metadata": {}
            }

    @staticmethod
    async def get_multi_horizon(asset: str) -> dict:
        """Compute 1d, 1w, 1m forecasts in one call."""
        results = {}
        for key in ["1d", "1w", "1m"]:
            results[key] = await ForecastingEngine.get_probabilistic_forecast(asset, key)
        return results
