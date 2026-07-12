"""Real OAuth and credential capture handlers for ShibaClaw WebUI."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import urllib.parse
import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse


def _base64url_encode(raw: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


async def start_generic_oauth(request: Request, job_id: str, jobs: dict, provider_name: str, display_name: str):
    """Start the provider-specific OAuth/credential flow."""
    jobs[job_id]["status"] = "running"
    jobs[job_id]["logs"].append(f"Starting connection flow for {display_name}...")

    # 1. xAI Device Code Flow (Real OAuth)
    if provider_name == "xai":
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://accounts.x.ai/oauth/device/code",
                    headers={"Accept": "application/json"},
                    json={
                        "client_id": "b1a00492-073a-47ea-816f-4c329264a828",
                        "scope": "openid profile email offline_access"
                    },
                    timeout=10,
                )
                resp_json = resp.json()

            user_code = resp_json.get("user_code")
            device_code = resp_json.get("device_code")
            verification_uri = resp_json.get("verification_uri") or "https://accounts.x.ai/oauth2/device"
            interval = resp_json.get("interval", 5)
            expires_in = resp_json.get("expires_in", 900)

            if not device_code or not user_code:
                # Fallback to key pasting if device flow fails
                return await _initiate_paste_flow(
                    job_id, jobs, "xai",
                    "https://console.x.ai/",
                    "⚠️ xAI Device Code flow failed to initialize. Please copy an API Key from the official xAI Console and paste it below:"
                )

            jobs[job_id]["status"] = "awaiting_code"
            jobs[job_id]["user_code"] = user_code
            jobs[job_id]["verification_uri"] = verification_uri
            jobs[job_id]["logs"].append(f"Go to: {verification_uri}")
            jobs[job_id]["logs"].append(f"Enter code: {user_code}")

            # Start polling in background
            asyncio.create_task(_poll_xai_token(job_id, jobs, device_code, interval, expires_in))

            return JSONResponse({
                "job_id": job_id,
                "user_code": user_code,
                "verification_uri": verification_uri,
                "status": "awaiting_code"
            })
        except Exception as e:
            return await _initiate_paste_flow(
                job_id, jobs, "xai",
                "https://console.x.ai/",
                f"⚠️ xAI Device Code flow error ({e}). Please manually copy an API Key from the official xAI Console and paste it below:"
            )

    return JSONResponse({"error": f"Unknown provider {provider_name}"}, status_code=400)


async def _initiate_paste_flow(job_id: str, jobs: dict, provider_name: str, console_url: str, instruction: str):
    """Sets up a local job to wait for the user pasting their key directly from the console tab."""
    jobs[job_id]["status"] = "awaiting_paste"
    jobs[job_id]["console_url"] = console_url
    jobs[job_id]["instruction"] = instruction
    
    event = asyncio.Event()
    holder = {"value": None}
    jobs[job_id]["_code_event"] = event
    jobs[job_id]["_code_holder"] = holder
    
    # Run the background listener
    asyncio.create_task(_await_paste_token(job_id, jobs, provider_name, event, holder))

    return JSONResponse({
        "job_id": job_id,
        "provider": provider_name,
        "status": "awaiting_paste",
        "console_url": console_url,
        "instruction": instruction
    })


async def _await_paste_token(job_id: str, jobs: dict, provider_name: str, event: asyncio.Event, holder: dict):
    """Wait for the user to submit the token using the standard WebUI code box."""
    try:
        # Await submission for up to 10 minutes
        await asyncio.wait_for(event.wait(), timeout=600.0)
        token = holder.get("value")
        if not token:
            raise ValueError("Token cannot be empty.")

        from shibaclaw.security.oauth_store import OAuthTokenStore
        store = OAuthTokenStore()
        store.save_token(provider_name, {"access_token": token.strip()})

        jobs[job_id]["status"] = "done"
        jobs[job_id]["logs"].append("✅ Authentication successful!")
    except asyncio.TimeoutError:
        if job_id in jobs and jobs[job_id]["status"] == "awaiting_paste":
            jobs[job_id]["status"] = "error"
            jobs[job_id]["logs"].append("❌ Connection timed out (10 minutes elapsed).")
    except Exception as exc:
        if job_id in jobs:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["logs"].append(f"❌ Error linking credentials: {exc}")


async def start_google_oauth(request: Request, job_id: str, jobs: dict, client_id: str, client_secret: str):
    """Start Google PKCE flow."""
    code_verifier = _base64url_encode(secrets.token_bytes(32))
    code_challenge = _base64url_encode(hashlib.sha256(code_verifier.encode("utf-8")).digest())

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/oauth/generic/callback?provider=google_gemini_cli&job_id={job_id}"

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={urllib.parse.quote(client_id)}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        "response_type=code&"
        "scope=https://www.googleapis.com/auth/generative-language&"
        "access_type=offline&"
        "prompt=consent&"
        f"code_challenge={urllib.parse.quote(code_challenge)}&"
        "code_challenge_method=S256&"
        f"state={job_id}"
    )

    jobs[job_id]["status"] = "awaiting_redirect"
    jobs[job_id]["auth_url"] = auth_url
    jobs[job_id]["_google_client_id"] = client_id
    jobs[job_id]["_google_client_secret"] = client_secret
    jobs[job_id]["_google_verifier"] = code_verifier
    jobs[job_id]["logs"].append("Initiating Google OAuth PKCE flow...")

    return JSONResponse({
        "job_id": job_id,
        "provider": "google_gemini_cli",
        "status": "awaiting_redirect",
        "auth_url": auth_url
    })


async def redirect_google_oauth(request: Request, job_id: str, client_id: str, client_secret: str):
    """Redirect user browser to Google OAuth authorization page (custom submit)."""
    from shibaclaw.webui.agent_manager import agent_manager
    jobs = agent_manager.oauth_jobs

    code_verifier = _base64url_encode(secrets.token_bytes(32))
    code_challenge = _base64url_encode(hashlib.sha256(code_verifier.encode("utf-8")).digest())

    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/oauth/generic/callback?provider=google_gemini_cli&job_id={job_id}"

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={urllib.parse.quote(client_id)}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        "response_type=code&"
        "scope=https://www.googleapis.com/auth/generative-language&"
        "access_type=offline&"
        "prompt=consent&"
        f"code_challenge={urllib.parse.quote(code_challenge)}&"
        "code_challenge_method=S256&"
        f"state={job_id}"
    )

    if job_id in jobs:
        jobs[job_id]["status"] = "awaiting_redirect"
        jobs[job_id]["auth_url"] = auth_url
        jobs[job_id]["_google_client_id"] = client_id
        jobs[job_id]["_google_client_secret"] = client_secret
        jobs[job_id]["_google_verifier"] = code_verifier
        jobs[job_id]["logs"].append("Redirecting to custom Google OAuth screen...")

    return RedirectResponse(url=auth_url)


async def _poll_xai_token(job_id: str, jobs: dict, device_code: str, interval: int, expires_in: int):
    """Background task to poll xAI token endpoint."""
    max_attempts = expires_in // interval
    for _ in range(max_attempts):
        await asyncio.sleep(interval)
        if job_id not in jobs or jobs[job_id]["status"] not in ("awaiting_code", "running"):
            return
        try:
            async with httpx.AsyncClient() as c:
                tr = await c.post(
                    "https://accounts.x.ai/oauth/token",
                    headers={"Accept": "application/json"},
                    json={
                        "client_id": "b1a00492-073a-47ea-816f-4c329264a828",
                        "device_code": device_code,
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    timeout=10,
                )
                tj = tr.json()

            error = tj.get("error")
            if error == "authorization_pending":
                continue
            elif error == "slow_down":
                await asyncio.sleep(5)
                continue
            elif error:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["logs"].append(f"❌ xAI error: {error}")
                return

            access_token = tj.get("access_token")
            if access_token:
                from shibaclaw.security.oauth_store import OAuthTokenStore
                store = OAuthTokenStore()
                store.save_token("xai", tj)
                jobs[job_id]["status"] = "done"
                jobs[job_id]["logs"].append("✅ Authenticated with xAI / Grok!")
                return
        except Exception as e:
            jobs[job_id]["logs"].append(f"Polling error: {e}")
            continue

    if job_id in jobs and jobs[job_id]["status"] == "awaiting_code":
        jobs[job_id]["status"] = "error"
        jobs[job_id]["logs"].append("❌ Timed out waiting for xAI authorization.")


# Legacy router functions - left for fallback or routing compat
async def api_oauth_generic_authorize(request: Request):
    return HTMLResponse("<html><body><h3>Not Active</h3></body></html>", status_code=404)


async def api_oauth_generic_callback(request: Request):
    """Handle callback response (Google redirect callback)."""
    from shibaclaw.webui.agent_manager import agent_manager
    jobs = agent_manager.oauth_jobs

    job_id = request.query_params.get("job_id", "")

    # GET redirect from Google OAuth
    google_code = request.query_params.get("code")
    google_state = request.query_params.get("state")

    if google_state:
        job_id = google_state

    job = jobs.get(job_id)
    if not job:
        return HTMLResponse("<html><body><h3>OAuth session expired</h3></body></html>", status_code=404)

    if google_code:
        try:
            client_id = job.get("_google_client_id")
            client_secret = job.get("_google_client_secret")
            code_verifier = job.get("_google_verifier")

            base_url = str(request.base_url).rstrip("/")
            redirect_uri = f"{base_url}/api/oauth/generic/callback?provider=google_gemini_cli&job_id={job_id}"

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": google_code,
                        "code_verifier": code_verifier,
                        "grant_type": "authorization_code",
                        "redirect_uri": redirect_uri
                    },
                    timeout=15
                )
                token_data = resp.json()

            if "error" in token_data:
                err_desc = token_data.get("error_description") or token_data.get("error")
                raise RuntimeError(f"Google API returned error: {err_desc}")

            from shibaclaw.security.oauth_store import OAuthTokenStore
            store = OAuthTokenStore()
            store.save_token("google_gemini_cli", token_data)

            job["status"] = "done"
            return HTMLResponse("<html><body><h2>Connection Successful</h2><script>window.close()</script></body></html>")
        except Exception as exc:
            job["status"] = "error"
            return HTMLResponse(f"<html><body><h2>Connection Failed</h2><p>{exc}</p></body></html>", status_code=400)

    error = request.query_params.get("error") or "Unknown error"
    job["status"] = "error"
    return HTMLResponse(f"<html><body><h2>OAuth Failed</h2><p>{error}</p></body></html>", status_code=400)
