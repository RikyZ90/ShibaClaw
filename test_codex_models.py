import asyncio
import httpx
from oauth_cli_kit import get_token as get_codex_token

async def fetch_models():
    try:
        token = await asyncio.to_thread(get_codex_token)
        headers = {"Authorization": f"Bearer {token.access}"}
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.openai.com/v1/models", headers=headers)
            print(resp.status_code)
            if resp.status_code == 200:
                print(resp.json())
            else:
                print(resp.text)
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(fetch_models())
