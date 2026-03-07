import os
import asyncio
import base64
import httpx
from datetime import datetime

# GitHub Config
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO_OWNER = os.environ.get("GITHUB_REPO_OWNER", "CLTWINGZ") # Default owner
GITHUB_REPO_NAME = os.environ.get("GITHUB_REPO_NAME", "AI-bot-backend") # Default repo
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
FILE_PATH = "data/prediction_history.csv" # Path relative to the root of the repo
LOCAL_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "prediction_history.csv")

SYNC_INTERVAL_SECS = 60 # Sync every 1 minute

async def sync_csv_to_github():
    """
    Reads the local prediction_history.csv and pushes it to GitHub using the REST API.
    Runs periodically as a background task.
    """
    print("DEBUG: Starting GitHub Auto-Sync background task...")
    
    while True:
        await asyncio.sleep(SYNC_INTERVAL_SECS)
        
        # 1. Verification checks
        if not GITHUB_TOKEN:
            print("GITHUB_SYNC WARNING: No GITHUB_TOKEN found in environment. Skipping sync.")
            continue
            
        if not os.path.exists(LOCAL_FILE_PATH):
            print("GITHUB_SYNC WARNING: prediction_history.csv not found locally. Skipping sync.")
            continue
            
        try:
            # 2. Read local file
            with open(LOCAL_FILE_PATH, "rb") as f:
                content = f.read()
            encoded_content = base64.b64encode(content).decode("utf-8")
            
            # 3. Get current file SHA from GitHub (required for updates)
            api_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/contents/{FILE_PATH}?ref={GITHUB_BRANCH}"
            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with httpx.AsyncClient() as client:
                get_res = await client.get(api_url, headers=headers)
                sha = None
                if get_res.status_code == 200:
                    sha = get_res.json().get("sha")
                    
                # 4. Push updated file via PUT request
                commit_message = f"Auto-Sync: Autopilot CSV Data Update ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                
                payload = {
                    "message": commit_message,
                    "content": encoded_content,
                    "branch": GITHUB_BRANCH
                }
                if sha:
                    payload["sha"] = sha
                    
                put_res = await client.put(api_url, headers=headers, json=payload)
                
                if put_res.status_code in [200, 201]:
                    print(f"GITHUB_SYNC SUCCESS: Successfully Pushed CSV at {datetime.now().strftime('%H:%M:%S')}")
                else:
                    print(f"GITHUB_SYNC ERROR: Failed to push file. Code: {put_res.status_code}, Body: {put_res.text}")
                
        except Exception as e:
            print(f"GITHUB_SYNC CRITICAL ERROR: {e}")
