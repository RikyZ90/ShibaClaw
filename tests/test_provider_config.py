from unittest.mock import MagicMock
from shibaclaw.agent.loop import ShibaBrain
from shibaclaw.cli.base import _make_provider
from shibaclaw.config.schema import Config


def test_gemini_uses_google_openai_compat_base_url():
    cfg = Config()
    cfg.agents.defaults.provider = "gemini"
    cfg.agents.defaults.model = "gemini/gemini-2.0-flash"

    assert cfg.get_provider_name(cfg.agents.defaults.model) == "gemini"
    assert (
        cfg.get_api_base(cfg.agents.defaults.model)
        == "https://generativelanguage.googleapis.com/v1beta/openai/"
    )


def test_auto_provider_match_accepts_raw_gemini_env_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    cfg = Config()
    cfg.agents.defaults.provider = "auto"
    cfg.agents.defaults.model = "gemini/gemini-2.0-flash"

    assert cfg.get_provider_name(cfg.agents.defaults.model) == "gemini"
    assert (
        cfg.get_api_base(cfg.agents.defaults.model)
        == "https://generativelanguage.googleapis.com/v1beta/openai/"
    )


def test_make_provider_accepts_env_only_gemini_configuration(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    cfg = Config()
    cfg.agents.defaults.provider = "auto"
    cfg.agents.defaults.model = "gemini/gemini-2.0-flash"

    provider = _make_provider(cfg, exit_on_error=False)

    assert provider is not None


def test_provider_config_strips_whitespace_from_api_base_and_key():
    from shibaclaw.config.loader import _migrate_secrets_from_raw_dict
    from unittest.mock import MagicMock

    mock_cm = MagicMock()

    raw = {
        "providers": {
            "custom": {
                "apiBase": "\thttp://localhost:1234/v1\t",
                "apiKey": "  lm-studio  \n",
            }
        }
    }

    _migrate_secrets_from_raw_dict(raw, mock_cm)
    cfg = Config.model_validate(raw)

    assert cfg.providers.custom.api_base == "http://localhost:1234/v1"
    mock_cm.set_secret.assert_called_with("providers", "custom.api_key", "  lm-studio  \n")


def test_shibabrain_resolves_provider_from_session_model(monkeypatch):
    import shibaclaw.cli.base as base_module

    cfg = Config.model_validate(
        {
            "agents": {"defaults": {"model": "openrouter/google/gemma-4-31b-it"}},
            "providers": {
                "openrouter": {"apiKey": "sk-or-test"},
                "githubCopilot": {},
            },
        }
    )

    created_models: list[str] = []

    def fake_make_provider(temp_cfg, exit_on_error=False):
        created_models.append(temp_cfg.agents.defaults.model)
        return f"provider:{temp_cfg.agents.defaults.model}"

    monkeypatch.setattr(base_module, "_make_provider", fake_make_provider)

    brain = object.__new__(ShibaBrain)
    brain.config = cfg
    brain.provider = "provider:default"
    brain.model = cfg.agents.defaults.model
    brain._provider_cache = {}

    resolved = ShibaBrain._resolve_provider_for_model(brain, "github_copilot/gpt-4.1")

    assert resolved == "provider:github_copilot/gpt-4.1"
    assert created_models == ["github_copilot/gpt-4.1"]


def test_shibabrain_ignores_forced_global_provider_for_session_override(monkeypatch):
    import shibaclaw.cli.base as base_module
    from unittest.mock import MagicMock

    mock_cm = MagicMock()
    mock_cm.get_secret.return_value = "sk-or-test"
    monkeypatch.setattr("shibaclaw.security.credential_manager.get_credential_manager", lambda: mock_cm)

    cfg = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "provider": "github_copilot",
                    "model": "github_copilot/gpt-4.1",
                }
            },
            "providers": {
                "openrouter": {},
                "githubCopilot": {},
            },
        }
    )

    created_models: list[str] = []

    def fake_make_provider(temp_cfg, exit_on_error=False):
        created_models.append(temp_cfg.agents.defaults.model)
        return f"provider:{temp_cfg.agents.defaults.model}"

    monkeypatch.setattr(base_module, "_make_provider", fake_make_provider)

    brain = object.__new__(ShibaBrain)
    brain.config = cfg
    brain.provider = "provider:github_copilot/gpt-4.1"
    brain.model = cfg.agents.defaults.model
    brain._provider_cache = {}

    resolved = ShibaBrain._resolve_provider_for_model(brain, "openrouter/google/gemma-4-31b-it")

    assert resolved == "provider:openrouter/google/gemma-4-31b-it"
    assert created_models == ["openrouter/google/gemma-4-31b-it"]


def test_shibabrain_steering_message_injection():
    brain = object.__new__(ShibaBrain)
    brain._steering_queues = {}
    
    assert brain.inject_steering_message("session_key_1", "Hello") is False
    assert "session_key_1" not in brain._steering_queues

    brain._steering_queues["session_key_1"] = []
    assert brain.inject_steering_message("session_key_1", "Steer instruction", media=["img.png"]) is True
    assert len(brain._steering_queues["session_key_1"]) == 1
    assert brain._steering_queues["session_key_1"][0]["content"] == "Steer instruction"
    assert brain._steering_queues["session_key_1"][0]["media"] == ["img.png"]


def test_save_turn_cleans_steering_prefix():
    brain = object.__new__(ShibaBrain)
    session = MagicMock()
    session.messages = []
    
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "**[USER INJECTION DURING TASK]**\n\nStop and change direction"}
    ]
    brain._save_turn(session, messages, skip=1)
    
    assert len(session.messages) == 1
    assert session.messages[0]["content"] == "Stop and change direction"

