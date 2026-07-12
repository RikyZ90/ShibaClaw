"""Generic mock OAuth flow for WebUI."""

from __future__ import annotations

import asyncio
from starlette.requests import Request
from starlette.responses import JSONResponse


async def start_generic_oauth(request: Request, job_id: str, jobs: dict, provider_name: str, display_name: str):
    """
    Start a generic 'mock' OAuth flow. Since real endpoints are not provided,
    this flow uses the 'awaiting_code' state to prompt the user to paste their 
    token/code directly in the WebUI, similar to a device flow.
    """
    loop = asyncio.get_running_loop()
    code_event = asyncio.Event()
    code_holder: dict[str, str] = {"value": ""}

    jobs[job_id]["_code_event"] = code_event
    jobs[job_id]["_code_holder"] = code_holder
    jobs[job_id]["status"] = "awaiting_code"
    
    # Fake URL to satisfy the UI requirement for an auth_url
    auth_url = f"https://mock-auth.openclaw.ai/authorize?provider={provider_name}&job_id={job_id}"
    jobs[job_id]["auth_url"] = auth_url
    
    jobs[job_id]["logs"].append(f"Starting connection flow for {display_name}.")
    jobs[job_id]["logs"].append("Please paste your access token or authorization code below to complete the connection.")

    async def _run_flow():
        try:
            # Wait for the user to submit the code via /api/oauth/code
            await asyncio.wait_for(code_event.wait(), timeout=900)
            token = code_holder["value"].strip()
            
            if not token:
                raise RuntimeError("No token or code was provided.")

            jobs[job_id]["logs"].append("Saving token securely...")
            
            # Save the token securely using OAuthTokenStore (compat with encrypted credentials)
            from shibaclaw.security.oauth_store import OAuthTokenStore
            store = OAuthTokenStore()
            store.save_token(provider_name, {"access_token": token})

            jobs[job_id]["status"] = "done"
            jobs[job_id]["logs"].append(f"✅ Authenticated with {display_name}!")
        except asyncio.TimeoutError:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["logs"].append("❌ Timed out waiting for token input.")
        except Exception as e:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["logs"].append(f"❌ Connection error: {e}")
        finally:
            loop.call_later(300, lambda: jobs.pop(job_id, None))

    asyncio.create_task(_run_flow())

    return JSONResponse(
        {
            "job_id": job_id,
            "provider": provider_name,
            "status": "awaiting_code",
            "auth_url": auth_url,
        }
    )
