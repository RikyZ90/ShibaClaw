"""OAuth helpers for the WebUI (GitHub Copilot, OpenRouter, and OpenAI Codex)."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import urllib.parse
import urllib.request

import httpx
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from .auth import get_auth_token

GITHUB_CLIENT_ID = "Iv1.b507a08c87ecfe98"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
OPENROUTER_AUTHORIZE_URL = "https://openrouter.ai/auth"
OPENROUTER_KEY_EXCHANGE_URL = "https://openrouter.ai/api/v1/auth/keys"
OPENROUTER_CALLBACK_PATH = "/api/oauth/openrouter/callback"
OPENROUTER_CALLBACK_BASE_URL_ENV = "SHIBACLAW_OPENROUTER_CALLBACK_BASE_URL"
OPENROUTER_TIMEOUT_SECONDS = 300


def _oauth_result_page(success: bool, message: str) -> str:
    title = "Login Successful" if success else "Login Failed"
    accent = "#4ade80" if success else "#f87171"
    return f"""
    <html>
      <body style="background:#0d0d0d;color:#f0f0f0;font-family:Inter,-apple-system,BlinkMacSystemFont,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
        <div style="max-width:520px;text-align:center;padding:24px;">
          <h2 style="margin:0 0 12px 0;color:{accent};">{title}</h2>
          <p style="margin:0;color:#a0a0a0;line-height:1.6;">{message}</p>
          <script>setTimeout(() => window.close(), 4000)</script>
        </div>
      </body>
    </html>
    """


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _openrouter_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "X-Title": "ShibaClaw",
        "HTTP-Referer": "https://github.com/RikyZ90/ShibaClaw",
    }
    if extra:
        headers.update(extra)
    return headers


def _resolve_openrouter_callback_base_url(request: Request) -> str:
    candidate = os.environ.get(OPENROUTER_CALLBACK_BASE_URL_ENV, "").strip()
    if not candidate:
        candidate = str(request.base_url)

    parsed = urllib.parse.urlsplit(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(
            f"{OPENROUTER_CALLBACK_BASE_URL_ENV} must be an absolute http(s) URL"
        )

    hostname = parsed.hostname or ""
    if hostname in ("127.0.0.1", "::1"):
        port = f":{parsed.port}" if parsed.port else ""
        parsed = urllib.parse.urlsplit(f"{parsed.scheme}://localhost{port}{parsed.path}")

    path = parsed.path.rstrip("/")
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _expire_openrouter_job(job_id: str, jobs: dict) -> None:
    job = jobs.get(job_id)
    if not job or job.get("status") != "awaiting_redirect":
        return
    job["status"] = "error"
    job["logs"].append("❌ Timed out waiting for the OpenRouter browser callback")
    asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))


def _cancel_openrouter_timeout(job: dict) -> None:
    timeout_handle = job.pop("_openrouter_timeout", None)
    if timeout_handle is not None:
        timeout_handle.cancel()


async def _exchange_openrouter_code_for_key(code: str, code_verifier: str) -> str:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            OPENROUTER_KEY_EXCHANGE_URL,
            headers=_openrouter_headers({"Content-Type": "application/json"}),
            json={
                "code": code,
                "code_verifier": code_verifier,
                "code_challenge_method": "S256",
            },
        )

    if not response.is_success:
        body = response.text.strip()
        raise RuntimeError(
            f"OpenRouter auth exchange failed ({response.status_code}): {body[:200]}"
        )

    payload = response.json()
    api_key = payload.get("key")
    if not api_key:
        raise RuntimeError("OpenRouter auth exchange succeeded but returned no API key")
    return api_key


async def _persist_openrouter_api_key(api_key: str) -> None:
    from shibaclaw.config.loader import save_config

    from .agent_manager import agent_manager

    if not agent_manager.config:
        agent_manager.load_latest_config()
    if not agent_manager.config:
        raise RuntimeError("No config loaded")

    cfg = agent_manager.config.model_copy(deep=True)
    cfg.providers.openrouter.api_key = api_key
    save_config(cfg)
    await agent_manager.reload_config(cfg)


async def start_openrouter_oauth(request: Request, job_id: str, jobs: dict):
    """Start the OpenRouter PKCE OAuth flow using the WebUI server as callback target."""
    code_verifier = _base64url_encode(secrets.token_bytes(32))
    code_challenge = _base64url_encode(hashlib.sha256(code_verifier.encode("utf-8")).digest())
    flow_token = secrets.token_urlsafe(16)
    callback_base_url = _resolve_openrouter_callback_base_url(request)
    callback_url = (
        callback_base_url
        + f"{OPENROUTER_CALLBACK_PATH}/{urllib.parse.quote(job_id)}/{urllib.parse.quote(flow_token)}"
    )
    auth_url = (
        f"{OPENROUTER_AUTHORIZE_URL}?callback_url={urllib.parse.quote(callback_url, safe='')}&"
        f"code_challenge={urllib.parse.quote(code_challenge)}&code_challenge_method=S256"
    )

    jobs[job_id]["status"] = "awaiting_redirect"
    jobs[job_id]["auth_url"] = auth_url
    jobs[job_id]["callback_url"] = callback_url
    jobs[job_id]["_openrouter_verifier"] = code_verifier
    jobs[job_id]["_openrouter_flow"] = flow_token
    jobs[job_id]["_openrouter_timeout"] = asyncio.get_event_loop().call_later(
        OPENROUTER_TIMEOUT_SECONDS, _expire_openrouter_job, job_id, jobs
    )
    jobs[job_id]["logs"].append("Open the URL below to sign in with OpenRouter.")
    jobs[job_id]["logs"].append(auth_url)
    jobs[job_id]["logs"].append("Waiting for browser callback...")

    return JSONResponse(
        {
            "job_id": job_id,
            "provider": "openrouter",
            "status": "awaiting_redirect",
            "auth_url": auth_url,
            "callback_url": callback_url,
        }
    )


async def finish_openrouter_oauth(request: Request, jobs: dict):
    """Handle the OpenRouter browser callback, exchange the code, and save the API key."""
    job_id = request.path_params.get("job_id", "") or request.query_params.get("job_id", "")
    flow_token = request.path_params.get("flow_token", "") or request.query_params.get("flow", "")
    code = request.query_params.get("code", "")
    error = request.query_params.get("error", "")
    error_message = request.query_params.get("message", "") or request.query_params.get("error_description", "")

    job = jobs.get(job_id)
    if not job:
        return HTMLResponse(
            _oauth_result_page(False, "This OpenRouter login flow is no longer active."),
            status_code=404,
        )

    _cancel_openrouter_timeout(job)

    if flow_token != job.get("_openrouter_flow"):
        job["status"] = "error"
        job["logs"].append("❌ OpenRouter callback rejected: flow token mismatch")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return HTMLResponse(
            _oauth_result_page(False, "The OpenRouter callback did not match the active login flow."),
            status_code=400,
        )

    if error:
        message = error_message or error
        job["status"] = "error"
        job["logs"].append(f"❌ OpenRouter authorization error: {message}")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return HTMLResponse(_oauth_result_page(False, message), status_code=400)

    if not code:
        job["status"] = "error"
        job["logs"].append("❌ OpenRouter callback missing authorization code")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return HTMLResponse(
            _oauth_result_page(False, "OpenRouter did not return an authorization code."),
            status_code=400,
        )

    code_verifier = job.get("_openrouter_verifier", "")
    if not code_verifier:
        job["status"] = "error"
        job["logs"].append("❌ OpenRouter callback arrived without an active PKCE verifier")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return HTMLResponse(
            _oauth_result_page(False, "The OpenRouter login flow is missing PKCE state."),
            status_code=400,
        )

    try:
        job["logs"].append("Exchanging authorization code for OpenRouter API key...")
        api_key = await _exchange_openrouter_code_for_key(code, code_verifier)
        await _persist_openrouter_api_key(api_key)
        job["status"] = "done"
        job["logs"].append("✅ OpenRouter API key saved to config")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return HTMLResponse(
            _oauth_result_page(True, "OpenRouter was connected successfully. You can close this window and return to ShibaClaw."),
            status_code=200,
        )
    except Exception as exc:
        job["status"] = "error"
        job["logs"].append(f"❌ OpenRouter login error: {exc}")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return HTMLResponse(_oauth_result_page(False, str(exc)), status_code=400)


async def start_github_oauth(job_id: str, jobs: dict):
    """Trigger GitHub device flow and poll for token in background."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                GITHUB_DEVICE_CODE_URL,
                headers={"Accept": "application/json"},
                json={"client_id": GITHUB_CLIENT_ID, "scope": "read:user"},
                timeout=10,
            )
            resp_json = resp.json()

        user_code = resp_json.get("user_code", "")
        verification_uri = resp_json.get("verification_uri", "https://github.com/login/device")
        device_code = resp_json.get("device_code", "")
        interval = resp_json.get("interval", 5)
        expires_in = resp_json.get("expires_in", 900)

        if not device_code or not user_code:
            return JSONResponse(
                {"error": "GitHub did not return a device code", "details": resp_json},
                status_code=502,
            )

        jobs[job_id]["logs"].append(f"Go to: {verification_uri}")
        jobs[job_id]["logs"].append(f"Enter code: {user_code}")
        jobs[job_id]["status"] = "awaiting_code"

        asyncio.create_task(_poll_github_token(job_id, jobs, device_code, interval, expires_in))

        return JSONResponse(
            {
                "job_id": job_id,
                "user_code": user_code,
                "verification_uri": verification_uri,
            }
        )
    except Exception as e:
        return JSONResponse({"error": f"Failed to contact GitHub: {e}"}, status_code=502)


async def _poll_github_token(job_id, jobs, device_code, interval, expires_in):
    max_attempts = expires_in // interval
    for _ in range(max_attempts):
        await asyncio.sleep(interval)
        try:
            async with httpx.AsyncClient() as c:
                tr = await c.post(
                    GITHUB_ACCESS_TOKEN_URL,
                    headers={"Accept": "application/json"},
                    json={
                        "client_id": GITHUB_CLIENT_ID,
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
                jobs[job_id]["logs"].append(f"❌ GitHub error: {error}")
                asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
                return

            access_token = tj.get("access_token")
            if access_token:
                home = os.path.expanduser("~")
                token_dir = os.path.join(home, ".shibaclaw", "github_copilot")
                os.makedirs(token_dir, exist_ok=True)
                with open(os.path.join(token_dir, "access-token"), "w") as f:
                    f.write(access_token)

                # Attempt gateway restart (use same host resolution as api.py)
                try:
                    from .agent_manager import agent_manager

                    if agent_manager.config and agent_manager.config.gateway:
                        gw = agent_manager.config.gateway
                        gw_port = gw.port
                        gateway_hostname = os.environ.get(
                            "SHIBACLAW_GATEWAY_HOST", "shibaclaw-gateway"
                        )
                        if gw.host in ("0.0.0.0", "::", ""):
                            targets = ["127.0.0.1", gateway_hostname]
                        else:
                            targets = [gw.host]
                        auth = get_auth_token()
                        for h in targets:
                            try:
                                req = urllib.request.Request(
                                    f"http://{h}:{gw_port}/restart", method="POST", data=b""
                                )
                                if auth:
                                    req.add_header("Authorization", f"Bearer {auth}")
                                urllib.request.urlopen(req, timeout=2)
                                break
                            except Exception:
                                continue
                except Exception:
                    pass

                jobs[job_id]["status"] = "done"
                jobs[job_id]["logs"].append("✅ Authenticated with GitHub Copilot!")
                asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
                return
        except Exception as e:
            jobs[job_id]["logs"].append(f"Poll error: {e}")
            continue

    jobs[job_id]["status"] = "error"
    jobs[job_id]["logs"].append("❌ Timed out waiting for authorization.")
    asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))


# ---------------------------------------------------------------------------
# OpenAI Codex OAuth — uses oauth-cli-kit's device flow via WebUI code input
# ---------------------------------------------------------------------------


async def start_codex_oauth(job_id: str, jobs: dict):
    try:
        from oauth_cli_kit.flow import _exchange_code_for_token_async
        from oauth_cli_kit.pkce import _create_state, _generate_pkce, _parse_authorization_input
        from oauth_cli_kit.providers import OPENAI_CODEX_PROVIDER
        from oauth_cli_kit.server import _start_local_server
        from oauth_cli_kit.storage import FileTokenStorage
    except ImportError:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["logs"].append("❌ oauth-cli-kit not installed (pip install oauth-cli-kit)")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return JSONResponse({"error": "oauth-cli-kit not installed"}, status_code=501)

    loop = asyncio.get_running_loop()
    code_event = asyncio.Event()
    code_holder: dict[str, str] = {"value": ""}

    jobs[job_id]["_code_event"] = code_event
    jobs[job_id]["_code_holder"] = code_holder
    jobs[job_id]["status"] = "awaiting_code"
    verifier, challenge = _generate_pkce()
    state = _create_state()
    params = {
        "response_type": "code",
        "client_id": OPENAI_CODEX_PROVIDER.client_id,
        "redirect_uri": OPENAI_CODEX_PROVIDER.redirect_uri,
        "scope": OPENAI_CODEX_PROVIDER.scope,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": OPENAI_CODEX_PROVIDER.default_originator,
    }
    auth_url = f"{OPENAI_CODEX_PROVIDER.authorize_url}?{urllib.parse.urlencode(params)}"
    jobs[job_id]["auth_url"] = auth_url
    jobs[job_id]["logs"].append("Open the URL below to sign in with OpenAI Codex.")
    jobs[job_id]["logs"].append(auth_url)

    code_future: asyncio.Future[str] = loop.create_future()

    def _notify(code_value: str) -> None:
        if code_future.done():
            return
        loop.call_soon_threadsafe(code_future.set_result, code_value)

    server, server_error = _start_local_server(state, on_code=_notify)
    if server_error:
        jobs[job_id]["logs"].append(
            f"Local callback server unavailable ({server_error}). Paste the callback URL or code below."
        )
    else:
        jobs[job_id]["logs"].append("Waiting for browser callback or pasted callback URL...")

    async def _wait_for_manual_code() -> str:
        await code_event.wait()
        return code_holder["value"]

    async def _run_flow():
        try:
            tasks = [asyncio.create_task(_wait_for_manual_code())]
            if server:
                tasks.append(asyncio.create_task(asyncio.wait_for(code_future, timeout=900)))

            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()

            raw_input = ""
            for task in done:
                try:
                    result = task.result()
                except asyncio.TimeoutError:
                    result = ""
                if result:
                    raw_input = result.strip()
                    break

            if not raw_input:
                raise RuntimeError("Authorization code not received")

            code, parsed_state = _parse_authorization_input(raw_input)
            if parsed_state and parsed_state != state:
                raise RuntimeError("State validation failed")
            if not code:
                raise RuntimeError("Authorization code not found")

            jobs[job_id]["logs"].append("Exchanging authorization code for tokens...")
            token = await _exchange_code_for_token_async(code, verifier, OPENAI_CODEX_PROVIDER)()
            FileTokenStorage(token_filename=OPENAI_CODEX_PROVIDER.token_filename).save(token)
            if token and getattr(token, "access", None):
                home = os.path.expanduser("~")
                cred_dir = os.path.join(home, ".config", "shibaclaw", "openai_codex")
                os.makedirs(cred_dir, exist_ok=True)
                cred_path = os.path.join(cred_dir, "credentials.json")
                with open(cred_path, "w") as f:
                    json.dump(
                        {
                            "access": token.access,
                            "refresh": getattr(token, "refresh", ""),
                            "expires": getattr(token, "expires", 0),
                            "account_id": getattr(token, "account_id", "unknown"),
                        },
                        f,
                    )

                jobs[job_id]["status"] = "done"
                account = getattr(token, "account_id", "unknown")
                jobs[job_id]["logs"].append(f"✅ Authenticated with OpenAI Codex ({account})")
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["logs"].append("❌ Authentication failed — no token received")
        except Exception as e:
            jobs[job_id]["status"] = "error"
            jobs[job_id]["logs"].append(f"❌ Codex login error: {e}")
        finally:
            if server:
                server.shutdown()
                server.server_close()
            loop.call_later(300, lambda: jobs.pop(job_id, None))

    asyncio.create_task(_run_flow())

    return JSONResponse(
        {
            "job_id": job_id,
            "provider": "openai_codex",
            "status": "awaiting_code",
            "auth_url": auth_url,
        }
    )
