"""Configuration loading utilities."""

import json
import os
import tempfile
from pathlib import Path

import pydantic
from loguru import logger

from shibaclaw.config.schema import Config

_current_config_path: Path | None = None
_plugins_onboarded = False


def set_config_path(path: Path) -> None:
    """Set the current config path (used to derive data directory)."""
    global _current_config_path
    _current_config_path = path


def get_config_path() -> Path:
    """Get the configuration file path."""
    if _current_config_path:
        return _current_config_path
    return Path.home() / ".shibaclaw" / "config.json"


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file or create default.

    Args:
        config_path: Optional path to config file. Uses default if not provided.

    Returns:
        Loaded configuration object.
    """
    global _plugins_onboarded
    path = config_path or get_config_path()

    if not path.exists():
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
        cfg = Config.model_validate(data)
        try:
            from shibaclaw.security.credential_manager import get_credential_manager
            cm = get_credential_manager()
            if cm.is_setup():
                if _migrate_config_secrets_inline(cfg, cm):
                    save_config(cfg, path)
        except Exception:
            logger.debug("[config] auto-migration of secrets to vault failed", exc_info=True)
        return cfg
    except (json.JSONDecodeError, ValueError, pydantic.ValidationError) as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        logger.warning("Using default configuration.")
        return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file atomically.

    Writes to a temporary file first, then renames it over the target so that
    a crash mid-write never leaves an empty or corrupt config.json.

    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(mode="json", by_alias=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False)

    # Write to a sibling temp file then rename — atomic on all major OSes.
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".config_tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, path)  # atomic rename
    except Exception:
        # Clean up the temp file on failure; re-raise so caller can log.
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
    # and strip any keys that should not reach ConnectedAppsConfig validation.
    # ConnectedAppsConfig uses extra="allow" so all keys are accepted;
    # we only need to guarantee the field exists as a dict.
    if "connectedApps" not in data:
        # try snake_case fallback (written by older versions)
        if "connected_apps" in data:
            data["connectedApps"] = data.pop("connected_apps")
    if data.get("connectedApps") is None:
        data["connectedApps"] = {}

    return data


def _migrate_config_secrets_inline(cfg: Config, cm) -> bool:
    """Move plain-text secrets from a Config object into the vault and zero them out."""
    from shibaclaw.config.schema import ProvidersConfig

    migrated = False

    # --- Provider API keys ---
    for field_name in ProvidersConfig.model_fields:
        provider_cfg = getattr(cfg.providers, field_name, None)
        if provider_cfg is None:
            continue
        if provider_cfg.api_key:
            cm.set_secret("providers", f"{field_name}.api_key", provider_cfg.api_key)
            provider_cfg.api_key = ""
            migrated = True

    # --- Web search API key ---
    if cfg.tools.web.search.api_key:
        cm.set_secret("tools", "web_search.api_key", cfg.tools.web.search.api_key)
        cfg.tools.web.search.api_key = ""
        migrated = True

    # --- Audio API key ---
    if cfg.audio.api_key:
        cm.set_secret("audio", "api_key", cfg.audio.api_key)
        cfg.audio.api_key = None
        migrated = True

    # --- Channel secrets (email password, bot tokens, etc.) ---
    if cfg.channels.model_extra:
        for ch_name, ch_data in cfg.channels.model_extra.items():
            if not isinstance(ch_data, dict):
                continue
            secret_keys = [
                k for k in ch_data
                if any(s in k.lower() for s in ("token", "password", "secret", "key"))
                and ch_data[k]
                and isinstance(ch_data[k], str)
            ]
            for sk in secret_keys:
                cm.set_secret("channels", f"{ch_name}.{sk}", ch_data[sk])
                ch_data[sk] = ""
                migrated = True

    # --- MCP OAuth secrets ---
    if cfg.tools and cfg.tools.mcp_servers:
        for server_name, server_cfg in cfg.tools.mcp_servers.items():
            if server_cfg.oauth and server_cfg.oauth.client_secret:
                cm.set_secret("mcp_servers", f"{server_name}.client_secret", server_cfg.oauth.client_secret)
                server_cfg.oauth.client_secret = None
                migrated = True

    return migrated

