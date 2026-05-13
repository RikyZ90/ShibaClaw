import json
import time


def test_check_for_update_uses_fresh_cache(tmp_path, monkeypatch):
    from shibaclaw.updater import checker

    cache_file = tmp_path / "update_cache.json"
    result = {
        "install_method": "pip",
        "current": "0.3.7",
        "latest": "0.3.8",
        "display_current": "0.3.7",
        "display_latest": "0.3.8",
        "update_available": True,
        "action_kind": "automatic",
        "action_label": "Update now",
        "action_command": "pip install --upgrade shibaclaw",
        "action_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
        "release_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
        "download_url": None,
        "manifest_url": "https://github.com/RikyZ90/ShibaClaw/releases/download/v0.3.8/update_manifest.json",
        "notification": None,
        "checked_at": int(time.time()),
        "error": None,
        "stale": False,
        "summary": "Version 0.3.8 is available on PyPI.",
        "notes": [],
    }

    cache_file.write_text(
        json.dumps(
            {
                "entries": {checker._cache_key("pip", "0.3.7"): result},
                "last_success": {checker._cache_key("pip", "0.3.7"): result},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(checker, "_CACHE_FILE", cache_file)
    monkeypatch.setattr(checker, "get_installation_method", lambda: "pip")
    monkeypatch.setattr(checker, "get_current_version", lambda: "0.3.7")
    monkeypatch.setattr(checker, "_check_pip", lambda current: (_ for _ in ()).throw(AssertionError("network should not run")))

    cached = checker.check_for_update()

    assert cached["latest"] == "0.3.8"
    assert cached["update_available"] is True


def test_check_for_update_falls_back_to_last_success(tmp_path, monkeypatch):
    from shibaclaw.updater import checker

    cache_file = tmp_path / "update_cache.json"
    stale = {
        "install_method": "pip",
        "current": "0.3.7",
        "latest": "0.3.8",
        "display_current": "0.3.7",
        "display_latest": "0.3.8",
        "update_available": True,
        "action_kind": "automatic",
        "action_label": "Update now",
        "action_command": "pip install --upgrade shibaclaw",
        "action_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
        "release_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
        "download_url": None,
        "manifest_url": "https://github.com/RikyZ90/ShibaClaw/releases/download/v0.3.8/update_manifest.json",
        "notification": None,
        "checked_at": 1,
        "error": None,
        "stale": False,
        "summary": "Version 0.3.8 is available on PyPI.",
        "notes": [],
    }
    cache_file.write_text(
        json.dumps(
            {
                "entries": {checker._cache_key("pip", "0.3.7"): stale},
                "last_success": {checker._cache_key("pip", "0.3.7"): stale},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(checker, "_CACHE_FILE", cache_file)
    monkeypatch.setattr(checker, "get_installation_method", lambda: "pip")
    monkeypatch.setattr(checker, "get_current_version", lambda: "0.3.7")
    monkeypatch.setattr(checker, "_check_pip", lambda current: (_ for _ in ()).throw(RuntimeError("boom")))

    cached = checker.check_for_update(force=True)

    assert cached["stale"] is True
    assert "boom" in cached["error"]
    assert cached["latest"] == "0.3.8"


def test_check_exe_uses_release_assets(monkeypatch):
    from shibaclaw.updater import checker

    monkeypatch.setattr(
        checker,
        "_request_json",
        lambda url: {
            "tag_name": "v0.3.8",
            "html_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
            "assets": [
                {
                    "name": "ShibaClaw-windows.zip",
                    "browser_download_url": "https://github.com/RikyZ90/ShibaClaw/releases/download/v0.3.8/ShibaClaw-windows.zip",
                },
                {
                    "name": "update_manifest.json",
                    "browser_download_url": "https://github.com/RikyZ90/ShibaClaw/releases/download/v0.3.8/update_manifest.json",
                },
            ],
        },
    )
    monkeypatch.setattr(checker, "fetch_manifest", lambda manifest_url: {"version": "0.3.8"})

    result = checker._check_exe("0.3.7")

    assert result["update_available"] is True
    assert result["download_url"].endswith("ShibaClaw-windows.zip")
    assert result["manifest_url"].endswith("update_manifest.json")
    assert result["action_kind"] == "manual-download"
    assert result["notification"]["category"] == "update"


def test_check_source_returns_manual_guidance_for_non_official_repo(tmp_path, monkeypatch):
    from shibaclaw.updater import checker

    monkeypatch.setattr(checker, "get_runtime_root_path", lambda: tmp_path)
    monkeypatch.setattr(checker, "is_official_repo_checkout", lambda root=None: False)

    result = checker._check_source("0.3.7")

    assert result["update_available"] is False
    assert result["action_kind"] == "manual-command"
    assert "official repository" in result["summary"]


def test_check_source_uses_release_manifest_for_official_repo(tmp_path, monkeypatch):
    from shibaclaw.updater import checker

    monkeypatch.setattr(checker, "get_runtime_root_path", lambda: tmp_path)
    monkeypatch.setattr(checker, "is_official_repo_checkout", lambda root=None: True)
    monkeypatch.setattr(
        checker,
        "_latest_release_info",
        lambda: {
            "latest": "0.3.8",
            "tagged_version": "0.3.8",
            "release_url": "https://github.com/RikyZ90/ShibaClaw/releases/tag/v0.3.8",
            "manifest_url": "https://github.com/RikyZ90/ShibaClaw/releases/download/v0.3.8/update_manifest.json",
            "download_url": "https://github.com/RikyZ90/ShibaClaw/releases/download/v0.3.8/ShibaClaw-windows.zip",
            "manifest": {"version": "0.3.8"},
            "manifest_error": None,
        },
    )

    result = checker._check_source("0.3.7")

    assert result["update_available"] is True
    assert result["latest"] == "0.3.8"
    assert result["manifest_url"].endswith("update_manifest.json")
    assert result["action_command"] == "git fetch --tags && git checkout v0.3.8 && pip install -e ."
    assert "release manifest" in result["summary"].lower()
