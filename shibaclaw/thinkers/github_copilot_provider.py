"""Github Copilot provider."""

import os
import time
from typing import Any

import httpx
from loguru import logger

from shibaclaw.thinkers.base import LLMResponse
from shibaclaw.thinkers.openai_provider import OpenAIThinker


class GithubCopilotThinker(OpenAIThinker):
    """
    Thinker for Github Copilot Chat API.

    Reads the OAuth access token (acquired via CLI login),
    exchanges it for a short-lived internal Copilot token,
    and calls the OpenAI-compatible Github Copilot endpoint.
    """

    _cached_token: str | None = None
    _token_expires_at: float = 0

    def __init__(self, default_model: str = "gpt-4o"):
        self._extra_headers = {
            "Editor-Version": "vscode/1.85.0",
            "Editor-Plugin-Version": "copilot-chat/0.11.1",
            "Openai-Organization": "github-copilot",
            "OpenAI-Intent": "conversation-panel",
            "User-Agent": "GithubCopilot/1.139.0",
        }

        # We start with empty key, will refresh dynamically in chat()
        super().__init__(
            api_key="dummy",
            api_base="https://api.githubcopilot.com",
            default_model=default_model,
            extra_headers=self._extra_headers,
        )

    async def _get_session_token(self) -> str:
        """Get or refresh the Copilot API session token."""
        now = time.time()
        if self._cached_token and now < (self._token_expires_at - 60):
            return self._cached_token

        # 1. Try environment variables
        env_token = os.environ.get("GITHUB_COPILOT_TOKEN")
        if env_token:
            access_token = env_token.strip()
        else:
            # 2. Try cached files
            home = os.path.expanduser("~")
            token_paths = [
                os.path.join(home, ".shibaclaw", "github_copilot", "access-token"),
            ]

            token_path = next((path for path in token_paths if os.path.exists(path)), None)
            if not token_path:
                raise ValueError(
                    "GitHub Copilot not authenticated. "
                    "Run `shibaclaw auth provider github_copilot` or use the WebUI to login."
                )

            with open(token_path, "r", encoding="utf-8") as f:
                access_token = f.read().strip()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.github.com/copilot_internal/v2/token",
                headers={
                    "Authorization": f"token {access_token}",
                    "Accept": "application/json",
                    "User-Agent": "shibaclaw/1.0",
                    "Editor-Version": "vscode/1.85.0",
                    "Editor-Plugin-Version": "copilot-chat/0.11.1",
                },
            )

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Failed to refresh Copilot token: {resp.status_code} - {resp.text}"
                )

            data = resp.json()
            self._cached_token = data.get("token")

            # The token usually includes expires_at in data, or roughly 30 minutes.
            expires_at = data.get("expires_at")
            if expires_at:
                self._token_expires_at = float(expires_at)
            else:
                self._token_expires_at = now + 25 * 60

            return self._cached_token or ""

    async def get_available_models(self) -> list[dict[str, str]]:
        try:
            session_token = await self._get_session_token()
            self._client.api_key = session_token
        except Exception as e:
            logger.error("Failed to authenticate GitHub Copilot while fetching models: {}", e)
            return []

        return await super().get_available_models()

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            session_token = await self._get_session_token()
            self._client.api_key = session_token
        except Exception as e:
            return LLMResponse(
                content=f"Error authenticating with Github Copilot: {e}", finish_reason="error"
            )

        return await super().chat(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
        )

    async def chat_streaming(
        self,
        messages: list[dict[str, Any]],
        on_token: Any = None,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            session_token = await self._get_session_token()
            self._client.api_key = session_token
        except Exception as e:
            return LLMResponse(
                content=f"Error authenticating with Github Copilot: {e}", finish_reason="error"
            )

        return await super().chat_streaming(
            messages=messages,
            on_token=on_token,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            reasoning_effort=reasoning_effort,
            tool_choice=tool_choice,
        )
