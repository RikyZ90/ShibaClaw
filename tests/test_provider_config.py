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
