"""Configuration schema using Pydantic."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from shibaclaw.thinkers.registry import ProviderSpec


class Base(BaseModel):
    """Base model that accepts both camelCase and snake_case keys."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChannelsConfig(Base):
    """Configuration for chat channels.

    Built-in and plugin channel configs are stored as extra fields (dicts).
    Each channel parses its own config in __init__.

    NOTE: model_config must repeat alias_generator + populate_by_name because
    overriding model_config in a subclass replaces the parent's ConfigDict
    entirely (Pydantic does not merge them).
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
    )

    send_progress: bool = True
    send_tool_hints: bool = False


class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.shibaclaw/workspace"
    model: str = ""
    provider: str = "auto"
    max_tokens: int = 8192
    context_window_tokens: int = 65_536
    temperature: float = 0.1
    max_tool_iterations: int = 40
    tool_timeout: int = 660
    loop_wall_timeout: int = 600
    subagent_timeout: int = 600
    reasoning_effort: str | None = None
    learning_enabled: bool = True
    learning_interval: int = 10
    memory_max_prompt_tokens: int = 2000
    memory_compact_threshold_tokens: int = 1600
    consolidation_model: str | None = None
    pinned_skills: list[str] = Field(default_factory=list)
    max_pinned_skills: int = 5


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)


class ProviderConfig(Base):
    """LLM provider configuration."""

    api_base: str | None = None
    extra_headers: dict[str, str] | None = None

    @field_validator("api_base", mode="before")
    @classmethod
    def _normalize_api_base(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value

    def resolve_api_key(self, provider_name: str = "") -> str:
        """Return the API key from the encrypted vault.

        Resolution order:
        1. Encrypted vault lookup under ``providers/<provider_name>.api_key``.
        2. Encrypted vault lookup under ``oauth_tokens/<provider_name>.access_token``.
        3. Empty string (caller should then try env vars).
        """
        if provider_name:
            try:
                from shibaclaw.security.credential_manager import get_credential_manager
                vault_key = get_credential_manager().get_secret("providers", f"{provider_name}.api_key")
                if vault_key and isinstance(vault_key, str):
                    return vault_key
            except Exception:
                pass
            try:
                from shibaclaw.security.credential_manager import get_credential_manager
                vault_token = get_credential_manager().get_secret("oauth_tokens", provider_name)
                if vault_token and isinstance(vault_token, dict) and vault_token.get("access_token"):
                    return vault_token["access_token"]
            except Exception:
                pass
        return ""


class ProvidersConfig(Base):
    """Configuration for LLM providers."""

    custom: ProviderConfig = Field(default_factory=ProviderConfig)
    azure_openai: ProviderConfig = Field(default_factory=ProviderConfig)
    anthropic: ProviderConfig = Field(default_factory=ProviderConfig)
    openai: ProviderConfig = Field(default_factory=ProviderConfig)
    openrouter: ProviderConfig = Field(
        default_factory=lambda: ProviderConfig(
            extra_headers={
                "HTTP-Referer": "https://github.com/RikyZ90/ShibaClaw",
                "X-Title": "ShibaClaw",
            }
        )
    )
    nvidia: ProviderConfig = Field(default_factory=ProviderConfig)
    deepseek: ProviderConfig = Field(default_factory=ProviderConfig)
    groq: ProviderConfig = Field(default_factory=ProviderConfig)
    zhipu: ProviderConfig = Field(default_factory=ProviderConfig)
    dashscope: ProviderConfig = Field(default_factory=ProviderConfig)
    vllm: ProviderConfig = Field(default_factory=ProviderConfig)
    ollama: ProviderConfig = Field(default_factory=ProviderConfig)
    gemini: ProviderConfig = Field(default_factory=ProviderConfig)
    moonshot: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax: ProviderConfig = Field(default_factory=ProviderConfig)
    aihubmix: ProviderConfig = Field(default_factory=ProviderConfig)
    siliconflow: ProviderConfig = Field(default_factory=ProviderConfig)
    volcengine: ProviderConfig = Field(default_factory=ProviderConfig)
    volcengine_coding_plan: ProviderConfig = Field(default_factory=ProviderConfig)
    byteplus: ProviderConfig = Field(default_factory=ProviderConfig)
    byteplus_coding_plan: ProviderConfig = Field(default_factory=ProviderConfig)
    openai_codex: ProviderConfig = Field(default_factory=ProviderConfig)
    github_copilot: ProviderConfig = Field(default_factory=ProviderConfig)
    google_gemini_cli: ProviderConfig = Field(default_factory=ProviderConfig)
    xai: ProviderConfig = Field(default_factory=ProviderConfig)
    qwen_oauth: ProviderConfig = Field(default_factory=ProviderConfig)
    minimax_portal: ProviderConfig = Field(default_factory=ProviderConfig)
    z_ai: ProviderConfig = Field(default_factory=ProviderConfig)


class HeartbeatConfig(Base):
    """Heartbeat service configuration."""

    enabled: bool = True
    interval_min: int = 30
    model: str | None = None
    session_key: str = "heartbeat:default"
    targets: dict[str, str] = Field(default_factory=dict)
    profile_id: str | None = None


class GatewayConfig(Base):
    """Gateway/server configuration."""

    host: str = "127.0.0.1"
    port: int = 19999
    ws_port: int = 19998
    heartbeat: HeartbeatConfig = Field(default_factory=HeartbeatConfig)
    rate_limit_per_minute: int = 0


class WebSearchConfig(Base):
    """Web search tool configuration."""

    provider: str = "brave"
    base_url: str = ""
    max_results: int = 5

    def resolve_api_key(self) -> str:
        """Return the API key from the encrypted vault."""
        try:
            from shibaclaw.security.credential_manager import get_credential_manager
            vault_key = get_credential_manager().get_secret("tools", "web_search.api_key")
            if vault_key and isinstance(vault_key, str):
                return vault_key
        except Exception:
            pass
        return ""


class AudioConfig(Base):
    """Configuration for Speech capabilities (STT/TTS)."""

    provider_url: str | None = None
    model: str = "whisper-large-v3-turbo"
    tts_enabled: bool = False
    tts_provider: str = "browser"
    tts_voice: str = "en_female"
    tts_speed: float = 1.0
    tts_lang: str = "en"
    tts_model_path: str | None = None

    def resolve_api_key(self) -> str | None:
        """Return the API key from the encrypted vault."""
        try:
            from shibaclaw.security.credential_manager import get_credential_manager
            vault_key = get_credential_manager().get_secret("audio", "api_key")
            if vault_key and isinstance(vault_key, str):
                return vault_key
        except Exception:
            pass
        return None


class WebToolsConfig(Base):
    """Web tools configuration."""

    proxy: str | None = None
    search: WebSearchConfig = Field(default_factory=WebSearchConfig)


class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    enable: bool = True
    timeout: int = 120
    path_append: str = ""
    install_audit: bool = True
    install_audit_timeout: int = 120
    install_audit_block_severity: str = "high"


class MCPOAuthConfig(Base):
    """
    OAuth 2.0 Authorization Code + PKCE configuration for a remote MCP server.

    Example config.json::

        "mcp_servers": {
          "notion": {
            "type": "streamableHttp",
            "url": "https://mcp.notion.com/mcp",
            "oauth": {
              "authUrl": "https://api.notion.com/v1/oauth/authorize",
              "tokenUrl": "https://api.notion.com/v1/oauth/token",
              "clientId": "<your-notion-integration-client-id>",
              "scopes": ["read_content", "update_content"]
            }
          }
        }
    """

    auth_url: str = Field(..., description="Provider's authorisation endpoint URL.")
    token_url: str = Field(..., description="Provider's token exchange endpoint URL.")
    client_id: str = Field(..., description="OAuth application client ID.")
    scopes: list[str] = Field(default_factory=list)
    callback_timeout: float = Field(default=120.0)

    def resolve_client_secret(self, server_name: str) -> str | None:
        """Return the client secret from the encrypted vault."""
        try:
            from shibaclaw.security.credential_manager import get_credential_manager
            vault_secret = get_credential_manager().get_secret("mcp_servers", f"{server_name}.client_secret")
            if vault_secret and isinstance(vault_secret, str):
                return vault_secret
        except Exception:
            pass
        return None


class MCPServerConfig(Base):
    """MCP server connection configuration (stdio or HTTP)."""

    type: Literal["stdio", "sse", "streamableHttp"] | None = None
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    headers: dict[str, str] = Field(default_factory=dict)
    oauth: MCPOAuthConfig | None = Field(default=None)
    tool_timeout: int = 30
    enabled_tools: list[str] = Field(default_factory=lambda: ["*"])
    klavis_app: str | None = Field(default=None, description="Connected App ID on Klavis Strata.")


class ToolsConfig(Base):
    """Tools configuration."""

    web: WebToolsConfig = Field(default_factory=WebToolsConfig)
    exec: ExecToolConfig = Field(default_factory=ExecToolConfig)
    restrict_to_workspace: bool = True
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class DesktopConfig(Base):
    """Desktop / native-launcher preferences."""

    close_behavior: str = "hide"
    start_hidden: bool = False
    auto_start_enabled: bool = False
    window_width: int = 920
    window_height: int = 1048


class ConnectedAppsConfig(Base):
    """Connected Apps (Klavis Strata) state storage.

    All dynamic keys (app states, __strata__, __backend__) are stored as Pydantic
    extra fields.  model_config must repeat alias_generator + populate_by_name
    because overriding model_config replaces — not merges — the parent ConfigDict.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="allow",
    )

    def get_extra(self, key: str) -> Any:
        """Helper to retrieve a dynamic extra field by key."""
        return self.model_extra.get(key) if self.model_extra else None


class Config(BaseSettings):
    """Root configuration for shibaclaw."""

    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    providers: ProvidersConfig = Field(default_factory=ProvidersConfig)
    gateway: GatewayConfig = Field(default_factory=GatewayConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    desktop: DesktopConfig = Field(default_factory=DesktopConfig)
    connected_apps: ConnectedAppsConfig = Field(
        default_factory=ConnectedAppsConfig,
        description="Connected Apps state — app OAuth status and Klavis Strata session metadata.",
    )

    @property
    def workspace_path(self) -> Path:
        """Get expanded workspace path."""
        return Path(self.agents.defaults.workspace).expanduser()

    @staticmethod
    def _provider_has_credentials(
        provider: "ProviderConfig | None", spec: "ProviderSpec | None"
    ) -> bool:
        if not provider:
            return False
        # Check encrypted vault
        if spec:
            resolved = provider.resolve_api_key(spec.name)
            if resolved:
                return True
        return bool(spec and spec.env_key and os.environ.get(spec.env_key))

    def _match_provider(
        self, model: str | None = None
    ) -> "tuple[ProviderConfig | None, str | None]":
        from shibaclaw.thinkers.registry import PROVIDERS

        forced = self.agents.defaults.provider
        if forced != "auto":
            p = getattr(self.providers, forced, None)
            return (p, forced) if p else (None, None)

        model_lower = (model or self.agents.defaults.model).lower()
        model_normalized = model_lower.replace("-", "_")
        model_prefix = model_lower.split("/", 1)[0] if "/" in model_lower else ""
        normalized_prefix = model_prefix.replace("-", "_")

        def _kw_matches(kw: str) -> bool:
            kw = kw.lower()
            return kw in model_lower or kw.replace("-", "_") in model_normalized

        def _get_valid_provider(spec: "ProviderSpec") -> "ProviderConfig | None":
            p = getattr(self.providers, spec.name, None)
            if p and (spec.is_oauth or spec.is_local or self._provider_has_credentials(p, spec)):
                return p
            return None

        if model_prefix:
            for spec in PROVIDERS:
                if normalized_prefix == spec.name:
                    p = _get_valid_provider(spec)
                    if p:
                        return p, spec.name

        for spec in PROVIDERS:
            if any(_kw_matches(kw) for kw in spec.keywords):
                p = _get_valid_provider(spec)
                if p:
                    return p, spec.name

        local_fallback: "tuple[ProviderConfig, str] | None" = None
        for spec in PROVIDERS:
            if not spec.is_local:
                continue
            p = getattr(self.providers, spec.name, None)
            if not (p and p.api_base):
                continue
            if spec.detect_by_base_keyword and spec.detect_by_base_keyword in p.api_base:
                return p, spec.name
            if local_fallback is None:
                local_fallback = (p, spec.name)
        if local_fallback:
            return local_fallback

        for spec in PROVIDERS:
            if spec.is_oauth:
                continue
            p = getattr(self.providers, spec.name, None)
            if self._provider_has_credentials(p, spec):
                return p, spec.name
        return None, None

    def get_provider(self, model: str | None = None) -> "ProviderConfig | None":
        p, _ = self._match_provider(model)
        return p

    def get_provider_name(self, model: str | None = None) -> "str | None":
        _, name = self._match_provider(model)
        return name

    def get_api_key(self, model: str | None = None) -> "str | None":
        p, name = self._match_provider(model)
        if not p:
            return None
        return p.resolve_api_key(name or "") or None

    def get_api_base(self, model: str | None = None) -> "str | None":
        from shibaclaw.thinkers.registry import find_by_name

        p, name = self._match_provider(model)
        if p and p.api_base:
            return p.api_base
        if name:
            spec = find_by_name(name)
            if (
                spec
                and spec.default_api_base
                and (spec.is_gateway or spec.is_local or spec.name == "gemini")
            ):
                return spec.default_api_base
        return None

    # SettingsConfigDict replaces (not merges) model_config — must include
    # extra="ignore" here so unknown root-level keys in config.json are
    # silently dropped instead of raising Extra inputs are not permitted.
    model_config = SettingsConfigDict(
        env_prefix="SHIBACLAW_",
        env_nested_delimiter="__",
        extra="ignore",
        alias_generator=to_camel,
        populate_by_name=True,
    )
