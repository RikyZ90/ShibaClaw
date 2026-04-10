"""OAuth device flow helpers for the WebUI (GitHub Copilot & OpenAI Codex)."""

from __future__ import annotations

import asyncio
import json
import httpx
import os
import urllib.request
from starlette.responses import JSONResponse
from .auth import get_auth_token

GITHUB_CLIENT_ID = "Iv1.b507a08c87ecfe98"
GITHUB_DEVICE_CODE_URL = "https://github.com/login/device/code"
GITHUB_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"

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
            return JSONResponse({"error": "GitHub did not return a device code", "details": resp_json}, status_code=502)

        jobs[job_id]["logs"].append(f"Go to: {verification_uri}")
        jobs[job_id]["logs"].append(f"Enter code: {user_code}")
        jobs[job_id]["status"] = "awaiting_code"

        asyncio.create_task(_poll_github_token(job_id, jobs, device_code, interval, expires_in))

        return JSONResponse({
            "job_id": job_id,
            "user_code": user_code,
            "verification_uri": verification_uri,
        })
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
            if error == "authorization_pending": continue
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
                token_dir = os.path.join(home, ".config", "shibaclaw", "github_copilot")
                os.makedirs(token_dir, exist_ok=True)
                with open(os.path.join(token_dir, "access-token"), "w") as f:
                    f.write(access_token)

                # Attempt gateway restart (use same host resolution as api.py)
                try:
                    from .agent_manager import agent_manager
                    if agent_manager.config and agent_manager.config.gateway:
                        gw = agent_manager.config.gateway
                        gw_port = gw.port
                        gateway_hostname = os.environ.get("SHIBACLAW_GATEWAY_HOST", "shibaclaw-gateway")
                        if gw.host in ("0.0.0.0", "::", ""):
                            targets = ["127.0.0.1", gateway_hostname]
                        else:
                            targets = [gw.host]
                        auth = get_auth_token()
                        for h in targets:
                            try:
                                req = urllib.request.Request(f"http://{h}:{gw_port}/restart", method="POST", data=b"")
                                if auth: req.add_header("Authorization", f"Bearer {auth}")
                                urllib.request.urlopen(req, timeout=2)
                                break
                            except Exception:
                                continue
                except Exception: pass

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
    """Trigger OpenAI Codex device flow via oauth-cli-kit.

    The library exposes ``login_oauth_interactive(print_fn, prompt_fn)``
    which drives a device-code flow.  We bridge its interactive callbacks
    to the WebUI by:
      • capturing printed URLs/codes via ``print_fn``  → pushed into job logs
      • blocking on ``prompt_fn`` via an asyncio.Event → the WebUI calls
        ``POST /api/oauth/code`` to deliver the user's input
    """
    try:
        from oauth_cli_kit import login_oauth_interactive  # noqa: F811
    except ImportError:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["logs"].append("❌ oauth-cli-kit not installed (pip install oauth-cli-kit)")
        asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))
        return JSONResponse({"error": "oauth-cli-kit not installed"}, status_code=501)

    code_event = asyncio.Event()
    code_holder: dict[str, str] = {"value": ""}

    # Store the event/holder so api_oauth_code can unblock the prompt
    jobs[job_id]["_code_event"] = code_event
    jobs[job_id]["_code_holder"] = code_holder
    jobs[job_id]["status"] = "awaiting_code"

    # Collect printed output (verification URL, user code, etc.)
    captured_lines: list[str] = []

    def _print(msg: str) -> None:
        captured_lines.append(msg)
        jobs[job_id]["logs"].append(msg)

    def _prompt_sync(msg: str) -> str:
        """Blocking prompt — will be called inside run_in_executor."""
        jobs[job_id]["logs"].append(f"⏳ {msg}")
        # Wait for the WebUI to deliver the code via api_oauth_code
        loop = asyncio.get_event_loop()
        future = asyncio.run_coroutine_threadsafe(code_event.wait(), loop)
        future.result(timeout=900)  # 15 min max
        return code_holder["value"]

    async def _run_flow():
        try:
            loop = asyncio.get_event_loop()
            token = await loop.run_in_executor(
                None,
                lambda: login_oauth_interactive(print_fn=_print, prompt_fn=_prompt_sync),
            )
            if token and getattr(token, "access", None):
                # Persist credentials to the same path the CLI uses
                home = os.path.expanduser("~")
                cred_dir = os.path.join(home, ".config", "shibaclaw", "openai_codex")
                os.makedirs(cred_dir, exist_ok=True)
                cred_path = os.path.join(cred_dir, "credentials.json")
                with open(cred_path, "w") as f:
                    json.dump({
                        "access": token.access,
                        "account_id": getattr(token, "account_id", "unknown"),
                    }, f)

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
            asyncio.get_event_loop().call_later(300, lambda: jobs.pop(job_id, None))

    asyncio.create_task(_run_flow())

    return JSONResponse({
        "job_id": job_id,
        "provider": "openai_codex",
        "status": "awaiting_code",
    })
