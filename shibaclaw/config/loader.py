"""Configuration loading utilities."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pydantic
from loguru import logger

from shibaclaw.config.schema import Config

_current_config_path: Path | None = None
_plugins_onboarded = False

# Sensitive field name fragments used by _scrub_secrets_from_dump
_SECRET_FRAGMENTS = ("token", "password", "secret", "key", "api_key", "apiKey")

_CHANNEL_SECRET_FIELDS = {
    ("telegram", "token"),
    ("discord", "token"),
    ("slack", "bot_token"),
    ("slack", "app_token"),
    ("email", "imap_password"),
    ("email", "smtp_password"),
    ("matrix", "access_token"),
    ("wecom", "secret"),
    ("dingtalk", "client_secret"),
    ("feishu", "app_secret"),
    ("feishu", "verification_token"),
    ("qq", "secret"),
    ("mochat", "claw_token"),
    ("whatsapp", "bridge_token"),
}


def set_config_path(path: Path) -> None:
    """Set the current config path (used to derive data directory)."""
    global _current_config_path
    _current_config_path = path


def get_config_path() -> Path:
    """Get the configuration file path."""
    if _current_config_path:
        return _current_config_path
    return Path.home() / ".shibaclaw" / "config.json"


def _scrub_secrets_from_dump(data: dict, cm: Any = None) -> dict:
    """Zero-out sensitive plaintext fields in a model_dump dict before writing to disk.

    This is a NO-OP when *cm* is None or when the vault is not set up
    (``cm.is_setup()`` returns False).  In that case the caller is not
    using the encrypted vault and secrets must remain in the JSON so
    they are not lost.

    When the vault IS active, _migrate_secrets_from_raw_dict() will have
    already moved every non-empty secret into the vault and popped it
    from *data* before this function is called.  This function therefore
    just acts as a belt-and-suspenders safety net to zero out any
    residual plaintext values that may have been re-introduced by a
    model_dump after migration.

    Operates in-place on *data* and also returns it for convenience.
    """
    # Only scrub when the vault is active.
    if cm is None:
        return data
    try:
        if not cm.is_setup():
            return data
    except Exception:
        return data

    def _clear_secret_fields(cfg: dict) -> None:
        for k in list(cfg):
            if (
                any(f in k.lower() for f in _SECRET_FRAGMENTS)
                and isinstance(cfg[k], str)
                and cfg[k]
            ):
                cfg[k] = ""

    # --- Provider API keys ---
    providers = data.get("providers", {})
    if isinstance(providers, dict):
        for provider_cfg in providers.values():
            if isinstance(provider_cfg, dict):
                _clear_secret_fields(provider_cfg)

    # --- Channel secrets ---
    channels = data.get("channels", {})
    if isinstance(channels, dict):
        for ch_name, ch_cfg in channels.items():
            if isinstance(ch_cfg, dict):
                import re
                for k in list(ch_cfg.keys()):
                    k_snake = re.sub(r'(?<!^)(?=[A-Z])', '_', k).lower()
                    if (ch_name.lower(), k_snake) in _CHANNEL_SECRET_FIELDS:
                        if isinstance(ch_cfg[k], str) and ch_cfg[k]:
                            ch_cfg[k] = ""

    # --- RAG API key ---
    rag = data.get("rag", {})
    if isinstance(rag, dict):
        _clear_secret_fields(rag)

    # --- Audio API key ---
    audio = data.get("audio", {})
    if isinstance(audio, dict):
        _clear_secret_fields(audio)

    # --- Web search API key ---
    tools = data.get("tools", {})
    if isinstance(tools, dict):
        web = tools.get("web", {})
        if isinstance(web, dict):
            search = web.get("search", {})
            if isinstance(search, dict):
                _clear_secret_fields(search)

        # --- MCP OAuth client secrets ---
        mcp_servers = tools.get("mcpServers", {}) or tools.get("mcp_servers", {})
        if isinstance(mcp_servers, dict):
            for server_cfg in mcp_servers.values():
                if not isinstance(server_cfg, dict):
                    continue
                oauth = server_cfg.get("oauth", {})
                if isinstance(oauth, dict):
                    _clear_secret_fields(oauth)

    # --- Connected Apps klavis_api_key ---
    connected_apps = data.get("connectedApps", {}) or data.get("connected_apps", {})
    if isinstance(connected_apps, dict):
        backend = connected_apps.get("__backend__")
        if isinstance(backend, dict) and backend.get("klavis_api_key"):
            backend["klavis_api_key"] = ""

    return data


def _get_cm_if_active() -> Any:
    """Return the credential manager if the vault is set up, else None."""
    try:
        from shibaclaw.security.credential_manager import get_credential_manager
        cm = get_credential_manager()
        if cm.is_setup() or cm._store_path.exists():
            return cm
        return None
    except Exception:
        return None


_CONFIG_CACHE: dict[tuple[str, int], Config] = {}


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        Loaded configuration object.
    """
    global _plugins_onboarded, _CONFIG_CACHE
    path = (config_path or get_config_path()).resolve()

    if path.exists():
        try:
            mtime_ns = path.stat().st_mtime_ns
            cache_key = (str(path), mtime_ns)
            if cache_key in _CONFIG_CACHE:
                return _CONFIG_CACHE[cache_key]
        except OSError:
            pass
    else:
        logger.info(f"Creating default configuration at {path}")
        default_cfg = Config()
        save_config(default_cfg, path)
        try:
            from shibaclaw.cli.onboard import _onboard_plugins
            _onboard_plugins(path)
            _plugins_onboarded = True
        except Exception:
            logger.debug("[config] _onboard_plugins failed on new config", exc_info=True)
        return default_cfg

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data = _migrate_config(data)
        if not _plugins_onboarded:
            try:
                from shibaclaw.cli.onboard import _onboard_plugins
                _onboard_plugins(path)
                _plugins_onboarded = True
                # Reload data in case onboarding modified the file
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data = _migrate_config(data)
            except Exception:
                logger.debug("[config] _onboard_plugins failed on existing config", exc_info=True)
        try:
            from shibaclaw.security.credential_manager import get_credential_manager
            cm = get_credential_manager()
            if cm.is_setup():
                if _migrate_secrets_from_raw_dict(data, cm):
                    # Save the raw data back (now without secrets) before validation
                    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as tmp:
                        json.dump(data, tmp, indent=2, ensure_ascii=False)
                        tmp_name = tmp.name
                    os.replace(tmp_name, path)
        except Exception:
            logger.debug("[config] auto-migration of secrets to vault failed", exc_info=True)

        cfg = Config.model_validate(data)
        try:
            mtime_ns = path.stat().st_mtime_ns
            _CONFIG_CACHE[(str(path), mtime_ns)] = cfg
        except OSError:
            pass
        return cfg
    except (json.JSONDecodeError, ValueError, pydantic.ValidationError) as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        logger.warning("Using default configuration.")
        return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file atomically.

    When the encrypted vault is active, sensitive fields that have already
    been migrated are zeroed-out before writing so the JSON never contains
    plaintext credentials.  When the vault is NOT active, secrets are
    preserved in the JSON as-is (they are the only copy).

    Writes to a temporary file first, then renames it over the target so
    that a crash mid-write never leaves an empty or corrupt config.json.

    Args:
        config: Configuration to save.
        config_path: Optional path to config file. Uses default if not provided.
    """
    global _CONFIG_CACHE
    _CONFIG_CACHE.clear()
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(mode="json", by_alias=True)
    # Only scrub when the vault is active (secrets already migrated there).
    cm = _get_cm_if_active()
    _scrub_secrets_from_dump(data, cm)
    payload = json.dumps(data, indent=2, ensure_ascii=False)

    # Write to a sibling temp file then rename — atomic on all major OSes.
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".config_tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, path)  # atomic rename
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _migrate_config(data: dict) -> dict:
    """Migrate old config formats to current."""
    # Move tools.exec.restrictToWorkspace → tools.restrictToWorkspace
    tools = data.get("tools", {})
    exec_cfg = tools.get("exec", {})
    if "restrictToWorkspace" in exec_cfg and "restrictToWorkspace" not in tools:
        tools["restrictToWorkspace"] = exec_cfg.pop("restrictToWorkspace")

    # Ensure email channel has all default fields (transparent migration)
    channels = data.get("channels", {})
    email = channels.get("email", {})
    email_defaults: dict = {
        "enabled": False,
        "consentGranted": False,
        "imapHost": "",
        "imapPort": 993,
        "imapUsername": "",
        "imapPassword": "",
        "imapUseSsl": True,
        "imapMailbox": "INBOX",
        "smtpHost": "",
        "smtpPort": 587,
        "smtpUsername": "",
        "smtpPassword": "",
        "smtpUseTls": True,
        "smtpUseSsl": False,
        "fromAddress": "",
        "autoReplyEnabled": True,
        "pollIntervalSeconds": 30,
        "markSeen": True,
        "maxBodyChars": 12000,
        "subjectPrefix": "Re: ",
        "allowFrom": [],
    }
    for key, default_val in email_defaults.items():
        if key not in email:
            email[key] = default_val
    channels["email"] = email

    # Remove stale consentGranted from non-email channels (UI bug legacy)
    for _ch_name, _ch_cfg in channels.items():
        if _ch_name != "email" and isinstance(_ch_cfg, dict):
            _ch_cfg.pop("consentGranted", None)
            _ch_cfg.pop("consent_granted", None)

    # Fix proxy saved as {} instead of null
    for _ch_name, _ch_cfg in channels.items():
        if isinstance(_ch_cfg, dict) and isinstance(_ch_cfg.get("proxy"), dict):
            _ch_cfg["proxy"] = None

    web_cfg = tools.get("web", {})
    if isinstance(web_cfg, dict) and isinstance(web_cfg.get("proxy"), dict):
        web_cfg["proxy"] = None

    data["channels"] = channels

    # Ensure mcpServers have all default fields
    mcp_servers = tools.get("mcpServers", {})
    mcp_defaults = {
        "type": None,
        "command": "",
        "args": [],
        "env": {},
        "url": "",
        "headers": {},
        "toolTimeout": 30,
        "enabledTools": ["*"],
    }
    for name, server in mcp_servers.items():
        for key, default_val in mcp_defaults.items():
            if key not in server:
                server[key] = default_val
    tools["mcpServers"] = mcp_servers
    data["tools"] = tools

    # Migrate connectedApps: if present, ensure it is a plain dict (not None)
    if "connectedApps" not in data:
        if "connected_apps" in data:
            data["connectedApps"] = data.pop("connected_apps")
    if data.get("connectedApps") is None:
        data["connectedApps"] = {}

    return data


def _provider_alias_to_snake(name: str) -> str:
    """Convert a camelCase provider alias to its snake_case spec name."""
    try:
        from shibaclaw.config.schema import ProvidersConfig
        for field_name, field_info in ProvidersConfig.model_fields.items():
            if field_info.alias == name or field_name == name:
                return field_name
    except Exception:
        pass
    return name


def _migrate_secrets_from_raw_dict(data: dict, cm: Any) -> bool:
    """Move plain-text secrets from a raw JSON dict into the vault and remove them."""
    migrated = False

    # --- Provider API keys ---
    providers = data.get("providers", {})
    if isinstance(providers, dict):
        for provider_name, provider_cfg in providers.items():
            if not isinstance(provider_cfg, dict):
                continue
            api_key = provider_cfg.pop("apiKey", None) or provider_cfg.pop("api_key", None)
            if api_key:
                snake_name = _provider_alias_to_snake(provider_name)
                cm.set_secret("providers", f"{snake_name}.api_key", api_key)
                migrated = True

    # --- Web search API key ---
    tools = data.get("tools", {})
    if isinstance(tools, dict):
        web = tools.get("web", {})
        if isinstance(web, dict):
            search = web.get("search", {})
            if isinstance(search, dict):
                api_key = search.pop("apiKey", None) or search.pop("api_key", None)
                if api_key:
                    cm.set_secret("tools", "web_search.api_key", api_key)
                    migrated = True

    # --- RAG API key ---
    rag = data.get("rag", {})
    if isinstance(rag, dict):
        key = rag.pop("apiKey", "") or rag.pop("api_key", "")
        if key:
            cm.set_secret("rag", "api_key", key)
            migrated = True

    # --- Audio API key ---
    audio = data.get("audio", {})
    if isinstance(audio, dict):
        api_key = audio.pop("apiKey", None) or audio.pop("api_key", None)
        if api_key:
            cm.set_secret("audio", "api_key", api_key)
            migrated = True

    # --- Channel secrets (email password, bot tokens, etc.) ---
    channels = data.get("channels", {})
    if isinstance(channels, dict):
        import re
        for ch_name, ch_data in channels.items():
            if not isinstance(ch_data, dict):
                continue
            
            for k in list(ch_data.keys()):
                val = ch_data[k]
                if not val or not isinstance(val, str):
                    continue
                    
                k_snake = re.sub(r'(?<!^)(?=[A-Z])', '_', k).lower()
                if (ch_name.lower(), k_snake) in _CHANNEL_SECRET_FIELDS:
                    ch_data.pop(k)
                    cm.set_secret("channels", f"{ch_name}.{k_snake}", val)
                    migrated = True

    # --- MCP OAuth secrets ---
    if isinstance(tools, dict):
        mcp_servers = tools.get("mcpServers", {}) or tools.get("mcp_servers", {})
        if isinstance(mcp_servers, dict):
            for server_name, server_cfg in mcp_servers.items():
                if not isinstance(server_cfg, dict):
                    continue
                oauth = server_cfg.get("oauth", {})
                if isinstance(oauth, dict):
                    client_secret = oauth.pop("clientSecret", None) or oauth.pop("client_secret", None)
                    if client_secret:
                        cm.set_secret("mcp_servers", f"{server_name}.client_secret", client_secret)
                        migrated = True

    # --- Connected Apps klavis_api_key ---
    connected_apps = data.get("connectedApps", {}) or data.get("connected_apps", {})
    if isinstance(connected_apps, dict):
        backend = connected_apps.get("__backend__")
        if isinstance(backend, dict):
            klavis_key = backend.pop("klavis_api_key", None)
            if klavis_key:
                cm.set_secret("connected_apps", "klavis_api_key", klavis_key)
                migrated = True

    return migrated
