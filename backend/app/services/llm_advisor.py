"""
LLM Advisor — Multi-Provider Financial Analysis Narrator
=========================================================
Priority order (first configured key wins):
  1. Google Gemini  — GEMINI_API_KEY  (free tier available at aistudio.google.com)
  2. OpenAI/Groq    — OPENAI_API_KEY  (set OPENAI_API_BASE for Groq or Ollama)
  3. Rule-based     — built-in fallback, no key needed
"""

import os
import httpx
import re

# ─────────────────────────────────────────────────────────────────────────────
FINANCIAL_SYSTEM_PROMPT = """You are CryptoInsight Alpha, an institutional-grade
quantitative financial analyst specialising in cryptocurrency markets.

Your job is to interpret the live quantitative signals below and synthesise them
into a crisp, professional analyst brief.

STRICT RULES:
1. Base ALL statements on the signal data provided — never hallucinate prices.
2. End EVERY response with: "⚠️ Not financial advice. Signals are probabilistic."
3. Format: 4–6 bullet points then one short paragraph.
4. Use ✅ for bullish, ⚠️ for neutral/caution, 🔻 for bearish.
5. Reference specific price levels from the signals.
6. When Elliott Wave, Fibonacci, SMC/FVG, RSI or Supertrend are mentioned,
   briefly explain *why* the level matters in 1 sentence.
"""

# ─────────────────────────────────────────────────────────────────────────────

async def llm_narrative(signals: dict, user_query: str) -> str:
    advisor = LLMAdvisor()
    perf_context = ""
    try:
        csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "prediction_history.csv")
        if os.path.exists(csv_path):
            import pandas as pd
            df_perf = pd.read_csv(csv_path)
            if not df_perf.empty:
                hits = int(df_perf['was_correct'].sum())
                total = len(df_perf)
                accuracy = (hits / total * 100)
                perf_context = (
                    f"\n[MODEL RELIABILITY CONTEXT]\n"
                    f"Past Performance: {hits}/{total} correct direction hits ({accuracy:.1f}% accuracy).\n"
                    f"Use this to weigh the confidence of your current forecast."
                )
    except Exception:
        pass

    signal_context = "\n".join(f"  • {k}: {v}" for k, v in signals.items())
    user_msg = (
        f"User question: {user_query}\n\n"
        f"Live signals from the quantitative engine:\n{signal_context}\n"
        f"{perf_context}\n\n"
        "Please provide your institutional market brief."
    )
    return await advisor.get_advice(user_msg)


class LLMAdvisor:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        # Sanitise: strip any stray leading characters before "AIza"
        if self.gemini_key and "AIza" in self.gemini_key:
            self.gemini_key = self.gemini_key[self.gemini_key.index("AIza"):]

    async def get_advice(self, prompt: str) -> str:
        if self.gemini_key and not self.gemini_key.startswith("your-") and len(self.gemini_key) > 20:
            return await self._gemini_narrative(self.gemini_key, prompt)

        if self.openai_key and not self.openai_key.startswith("your-"):
            return await self._openai_narrative(self.openai_key, prompt)

        return self._rule_based_narrative({}, prompt)

    async def _gemini_narrative(self, api_key: str, user_msg: str) -> str:
        model = os.environ.get("GEMINI_MODEL", "gemini-flash-latest") 

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )
        
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{FINANCIAL_SYSTEM_PROMPT}\n\n{user_msg}"}]
                }
            ],
            "generationConfig": {
                "temperature": 0.4,
                "maxOutputTokens": 800,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    err_json = {}
                    try: err_json = resp.json(); 
                    except: pass
                    err_msg = err_json.get("error", {}).get("message", resp.text[:100])
                    return f"[Gemini API Error {resp.status_code}: {err_msg}]\n\n" + self._rule_based_narrative({}, user_msg)
                
                data = resp.json()
                if not data.get("candidates") or not data["candidates"][0].get("content"):
                    return "[Gemini Response Empty or Blocked]\n\n" + self._rule_based_narrative({}, user_msg)
                    
                return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"[Gemini Connection Error: {str(e)}]\n\n" + self._rule_based_narrative({}, user_msg)

    async def _openai_narrative(self, api_key: str, user_msg: str) -> str:
        api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
        model    = os.environ.get("LLM_MODEL", "gpt-3.5-turbo")
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{api_base}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": FINANCIAL_SYSTEM_PROMPT},
                            {"role": "user",   "content": user_msg},
                        ],
                        "max_tokens": 512,
                        "temperature": 0.4,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"[OpenAI/Groq error: {e}]\n\n" + self._rule_based_narrative({}, user_msg)

    def _rule_based_narrative(self, signals: dict, user_query: str) -> str:
        asset      = signals.get("asset", "BTC")
        price      = signals.get("current_price", None)
        trend      = signals.get("trend", "")

        bullish  = "bullish" in trend.lower() or "golden" in trend.lower()
        icon     = "✅" if bullish else "🔻"

        lines = [f"**{asset}/USDT Institutional Brief** {icon}\n"]
        if price: lines.append(f"- **Price:** ${price:,.2f}")
        lines.append(f"- **Structure:** {trend}")
        lines.append("\n> ⚠️ Not financial advice. Signals are probabilistic.")
        return "\n".join(lines)
