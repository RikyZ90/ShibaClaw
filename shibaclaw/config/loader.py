"""Configuration loading utilities."""

import json
from pathlib import Path

import pydantic
from loguru import logger

from shibaclaw.config.schema import Config

_current_config_path: Path | None = None


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
    path = config_path or get_config_path()

    if not path.exists():
        logger.info(f"Creating default configuration at {path}")
        default_cfg = Config()
        save_config(default_cfg, path)
        # Sync plugin/channel defaults
        try:
            from shibaclaw.cli.onboard import _onboard_plugins
            _onboard_plugins(path)
        except Exception:
            logger.debug("[config] _onboard_plugins failed on new config", exc_info=True)
        return default_cfg

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data = _migrate_config(data)
        try:
            from shibaclaw.cli.onboard import _onboard_plugins
            _onboard_plugins(path)
        except Exception:
            logger.debug("[config] _onboard_plugins failed on existing config", exc_info=True)
        return Config.model_validate(data)
    except (json.JSONDecodeError, ValueError, pydantic.ValidationError) as e:
        logger.warning(f"Failed to load config from {path}: {e}")
        logger.warning("Using default configuration.")
        return Config()


def save_config(config: Config, config_path: Path | None = None) -> None:
    """
    Save configuration to file.

    Args:
        config: Configuration to save.
        config_path: Optional path to save to. Uses default if not provided.
    """
    path = config_path or get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump(mode="json", by_alias=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
    _EMAIL_DEFAULTS: dict = {
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
    for key, default_val in _EMAIL_DEFAULTS.items():
        if key not in email:
            email[key] = default_val
    channels["email"] = email

    # Remove stale consentGranted from non-email channels (UI bug legacy)
    for _ch_name, _ch_cfg in channels.items():
        if _ch_name != "email" and isinstance(_ch_cfg, dict):
            _ch_cfg.pop("consentGranted", None)
            _ch_cfg.pop("consent_granted", None)

    # Fix proxy saved as {} instead of null (caused by typeof null === "object" in JS)
    for _ch_name, _ch_cfg in channels.items():
        if isinstance(_ch_cfg, dict) and isinstance(_ch_cfg.get("proxy"), dict):
            _ch_cfg["proxy"] = None

    data["channels"] = channels

    # Ensure mcpServers have all default fields without re-adding deleted servers
    mcp_servers = tools.get("mcpServers", {})
    _MCP_DEFAULTS = {
        "type": None,
        "command": "",
        "args": [],
        "env": {},
        "url": "",
        "headers": {},
        "toolTimeout": 30,
        "enabledTools": ["*"]
    }
    if not mcp_servers:
        mcp_servers["mcp"] = dict(_MCP_DEFAULTS)
    else:
        for name, server in mcp_servers.items():
            for key, default_val in _MCP_DEFAULTS.items():
                if key not in server:
                    server[key] = default_val
    tools["mcpServers"] = mcp_servers
    data["tools"] = tools

    return data
