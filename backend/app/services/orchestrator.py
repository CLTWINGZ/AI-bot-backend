from .risk_controls import RiskManager
from .forecasting import ForecastingEngine, run_macd_multi_backtest
from .market_data import MarketDataCheck
from .research import ResearchAgent
from .analysis import AnalysisEngine
from .pattern_recognition import PatternBot
from .llm_advisor import llm_narrative
from ..models.chat import ChatRequest, ChatResponse
import re

MULTI_HORIZON_KEYWORDS = [
    "next day", "next week", "next month", "1 day", "1 week", "1 month",
    "daily forecast", "weekly forecast", "monthly forecast",
    "tomorrow", "this week", "this month", "30 day", "7 day",
]

class ChatOrchestrator:
    @staticmethod
    async def process(request: ChatRequest) -> ChatResponse:
        """
        Orchestration Layer for crypto analysis matching supervisory expectations.
        Separates language routing from deterministic/probabilistic models.
        """
        msg = request.message.lower()
        
        # 1. Check for Unsafe Intent (Risk Guardrails)
        if RiskManager.identify_unsafe_intent(msg):
            warning_msg = RiskManager.craft_warning_dialog(msg)
            return ChatResponse(
                message=warning_msg,
                intent_detected="high_risk_flagged",
                is_warning=True,
                metadata={"action": "suitability_gating_triggered"}
            )
            
        # 2a. MACD Multi-Timeframe Backtest
        BACKTEST_KEYWORDS = [
            "backtest", "back test", "back-test",
            "macd backtest", "macd back", "macd signal",
            "strategy test", "win rate", "strategy performance",
            "signal accuracy", "macd multi", "timeframe test",
        ]
        if any(kw in msg for kw in BACKTEST_KEYWORDS):
            asset = "BTC"
            if "eth" in msg or "ethereum" in msg: asset = "ETH"
            elif "sol" in msg or "solana" in msg: asset = "SOL"
            elif "bnb" in msg:                    asset = "BNB"
            elif "xrp" in msg:                    asset = "XRP"
            elif "ada" in msg:                    asset = "ADA"

            bt_result = await run_macd_multi_backtest(asset)
            return ChatResponse(
                message=bt_result,
                intent_detected="macd_backtest",
                metadata={"asset": asset, "strategy": "MACD_crossover_multi_TF"}
            )

        # 2b. Multi-Horizon Forecast (next day / week / month)
        if any(kw in msg for kw in MULTI_HORIZON_KEYWORDS):
            asset = "BTC"
            if "eth" in msg or "ethereum" in msg: asset = "ETH"
            elif "sol" in msg: asset = "SOL"

            # Determine which horizons the user asked about
            horizons = []
            if any(w in msg for w in ["day", "24h", "tomorrow"]):   horizons.append("1d")
            if any(w in msg for w in ["week", "7d", "weekly"]):      horizons.append("1w")
            if any(w in msg for w in ["month", "30d", "monthly"]):   horizons.append("1m")
            if not horizons:
                horizons = ["1d", "1w", "1m"]  # if none specified, return all

            parts = []
            all_meta = {}
            for h in horizons:
                fc = await ForecastingEngine.get_probabilistic_forecast(asset, h)
                parts.append(fc["message"])
                all_meta[h] = fc["metadata"]

            combined_fc = "\n\n---\n\n".join(parts)
            llm_text = await llm_narrative(
                signals={"asset": asset, "multi_horizon_forecasts": str(all_meta)[:600]},
                user_query=request.message
            )
            return ChatResponse(
                message=combined_fc + "\n\n---\n\n**🤖 Gemini AI Insight:**\n" + llm_text,
                intent_detected="multi_horizon_forecast",
                metadata={"asset": asset, "horizons": horizons, "forecasts": all_meta}
            )

        # 2c. Standard single-horizon Probabilistic Forecast
        horizon_match = re.search(r"(\d+)(h|d|m)", msg)
        is_forecast_intent = "forecast" in msg or "predict" in msg or "next" in msg or "expect" in msg
        
        if is_forecast_intent or horizon_match:
            asset = "ETH" # default extraction mock
            if "btc" in msg or "bitcoin" in msg:
                asset = "BTC"
            elif "sol" in msg or "solana" in msg:
                asset = "SOL"
            
            horizon = horizon_match.group(0) if horizon_match else "24h"
                
            forecast_data = await ForecastingEngine.get_probabilistic_forecast(asset, horizon=horizon)
            return ChatResponse(
                message=forecast_data["message"],
                intent_detected="probabilistic_forecast",
                metadata={"forecast": forecast_data["metadata"], "horizon": horizon}
            )
            
        # 3. Check for Deep Research / RAG
        if "research" in msg or "blackrock" in msg or "architecture" in msg:
            research_response = ResearchAgent.get_research_response(msg)
            return ChatResponse(
                message=research_response,
                intent_detected="knowledge_retrieval",
                metadata={"source": "institutional_corpus_RAG_mock"}
            )
            
        # 4a. Chart Pattern + 1m Analysis — Elliott Wave, SMC, FVG, RSI, Fib
        PATTERN_KEYWORDS = [
            # Classic TA
            "elliott", "wave", "smc", "fvg", "orderblock", "order block",
            "pattern", "chart", "cross", "golden cross", "death cross",
            "fibonacci", "fib", "supertrend", "rsi", "divergence",
            "market analysis", "ema", "sma", "macd",
            "1 minute", "1min", "1m chart", "intraday",
            # ICT concepts
            "ict", "inner circle", "order block", "institutional",
            "kill zone", "killzone", "liquidity", "sweep",
            "break of structure", "bos", "choch", "change of character",
            "fair value gap", "premium", "discount", "equilibrium",
            "buy side", "sell side", "smart money",
        ]
        if any(keyword in msg for keyword in PATTERN_KEYWORDS):
            asset = "BTC" if ("btc" in msg or "bitcoin" in msg) else "ETH"
            if "etc" in msg: asset = "ETC"
            if "sol" in msg: asset = "SOL"

            # Choose interval from message
            interval = "15m"
            if "1 minute" in msg or "1min" in msg or "1m " in msg:  interval = "1m"
            elif "5 min" in msg or "5m" in msg:                      interval = "5m"
            elif "1 hour" in msg or "1h" in msg:                     interval = "1h"
            elif "4 hour" in msg or "4h" in msg:                     interval = "4h"
            elif "daily" in msg or "1d" in msg:                      interval = "1d"

            pattern_response = await PatternBot.analyze_patterns(asset, interval=interval)

            # Build a rich signal dict for Gemini to narrate
            signals = {
                "asset": asset, "interval": interval,
                "analysis_summary": pattern_response[:800],
            }
            llm_text = await llm_narrative(signals=signals, user_query=request.message)
            combined = pattern_response + "\n\n---\n\n**🤖 Gemini AI Insight:**\n" + llm_text
            return ChatResponse(
                message=combined,
                intent_detected="chart_pattern_analysis",
                metadata={"asset": asset, "interval": interval, "llm": "gemini"}
            )

        # 4b. Generic Live Analysis (Technical, Fundamental, News)
        if any(keyword in msg for keyword in ["analysis", "technical", "fundamental", "news", "ta", "fa"]):
            analysis_response = await AnalysisEngine.get_live_analysis(msg)
            asset = "BTC" if "btc" in msg or "bitcoin" in msg else "ETH"
            llm_text = await llm_narrative(
                signals={"asset": asset, "raw_analysis": analysis_response[:600]},
                user_query=request.message
            )
            combined = analysis_response + "\n\n---\n\n**🤖 Gemini AI Insight:**\n" + llm_text
            return ChatResponse(
                message=combined,
                intent_detected="live_analysis",
                metadata={"source": "live_data_api", "llm": "gemini"}
            )

        # 5. Default: Live Market Snapshot + Gemini Narrative
        snapshot = await MarketDataCheck.get_summary()
        llm_text = await llm_narrative(
            signals={"raw_snapshot": snapshot[:400]},
            user_query=request.message
        )
        combined = snapshot + "\n\n---\n\n**🤖 Gemini AI Insight:**\n" + llm_text
        return ChatResponse(
            message=combined,
            intent_detected="market_snapshot",
            metadata={"source": "binance_live", "llm": "gemini"}
        )
