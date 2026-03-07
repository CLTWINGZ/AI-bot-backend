import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        # Wait until the local server is spun up 
        print("Testing GET /api/settings...")
        res1 = await client.get("http://localhost:8000/api/settings")
        print("GET Status:", res1.status_code)
        print("GET Body:", res1.text)

        print("Testing POST /api/settings...")
        res2 = await client.post("http://localhost:8000/api/settings", json={
            "gemini_api_key": "test_gemini",
            "openai_api_key": "test_openai",
            "openai_api_base": "https://api.openai.com/v1",
            "llm_model": "gpt-3.5-turbo"
        })
        print("POST Status:", res2.status_code)
        print("POST Body:", res2.text)

asyncio.run(test())
