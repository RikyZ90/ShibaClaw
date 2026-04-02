"""Tests for shibaclaw.updater — checker, manifest."""

from __future__ import annotations

import json
import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── Helpers ──────────────────────────────────────────────────────────────────

def _fake_urlopen(payload: dict | bytes, status: int = 200):
    """Return a context-manager mock that behaves like urllib.request.urlopen."""
    if isinstance(payload, dict):
        body = json.dumps(payload).encode()
    else:
        body = payload

    cm = MagicMock()
    cm.__enter__ = lambda s: s
    cm.__exit__ = MagicMock(return_value=False)
    cm.read.return_value = body
    cm.status = status
    return cm


# ── checker.py ────────────────────────────────────────────────────────────────

class TestChecker:
    """Tests for shibaclaw.updater.checker."""

    def setup_method(self):
        # Use a temp dir for the cache file so tests don't touch real ~/.shibaclaw
        self._tmp = tempfile.mkdtemp()
        self._cache_patch = patch(
            "shibaclaw.updater.checker._CACHE_FILE",
            Path(self._tmp) / "update_cache.json",
        )
        self._cache_patch.start()

    def teardown_method(self):
        self._cache_patch.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_update_available(self):
        """Newer tag on GitHub → update_available True."""
        github_resp = {
            "tag_name": "v99.0.0",
            "html_url": "https://github.com/example",
            "assets": [{"name": "update_manifest.json", "browser_download_url": "https://example.com/manifest.json"}],
        }
        with patch("urllib.request.urlopen", return_value=_fake_urlopen(github_resp)):
            from shibaclaw.updater.checker import check_for_update
            result = check_for_update(force=True)

        assert result["update_available"] is True
        assert result["latest"] == "99.0.0"
        assert result["manifest_url"] == "https://example.com/manifest.json"

    def test_no_update(self):
        """Same tag as current → update_available False."""
        from shibaclaw import __version__
        github_resp = {
            "tag_name": f"v{__version__}",
            "html_url": "https://github.com/example",
            "assets": [],
        }
        with patch("urllib.request.urlopen", return_value=_fake_urlopen(github_resp)):
            from shibaclaw.updater.checker import check_for_update
            result = check_for_update(force=True)

        assert result["update_available"] is False

    def test_prerelease_same_numeric_no_update(self):
        """0.0.7a vs 0.0.7 current → no update (same numeric base)."""
        from shibaclaw import __version__
        github_resp = {
            "tag_name": f"v{__version__}a",
            "html_url": "https://github.com/example",
            "assets": [],
        }
        with patch("urllib.request.urlopen", return_value=_fake_urlopen(github_resp)):
            from shibaclaw.updater.checker import check_for_update
            result = check_for_update(force=True)

        assert result["update_available"] is False

    def test_prerelease_higher_numeric_triggers_update(self):
        """0.0.8a > 0.0.7 current → update triggered."""
        github_resp = {
            "tag_name": "v0.0.8a",
            "html_url": "https://github.com/example",
            "assets": [],
        }
        with patch("urllib.request.urlopen", return_value=_fake_urlopen(github_resp)):
            from shibaclaw.updater.checker import check_for_update
            result = check_for_update(force=True)

        assert result["update_available"] is True

    def test_network_error_is_captured(self):
        """Network failure → error key populated, no crash."""
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")):
            from shibaclaw.updater.checker import check_for_update
            result = check_for_update(force=True)

        assert result["error"] is not None
        assert result["update_available"] is False

    def test_result_is_cached(self):
        """Second call without force= should return cache, not hit GitHub."""
        github_resp = {
            "tag_name": "v99.0.0",
            "html_url": "https://github.com/example",
            "assets": [],
        }
        cache_path = Path(self._tmp) / "update_cache.json"
        import shibaclaw.updater.checker as checker_mod
        with patch.object(checker_mod, "_CACHE_FILE", cache_path), \
             patch("urllib.request.urlopen", return_value=_fake_urlopen(github_resp)) as mock_open:
            checker_mod.check_for_update(force=True)   # hits GitHub, writes cache
            checker_mod.check_for_update(force=False)  # should use cache, not hit GitHub

        assert mock_open.call_count == 1  # GitHub called only once

    def test_invalidate_cache_removes_file(self):
        """invalidate_cache() should delete the cache file."""
        from shibaclaw.updater.checker import _CACHE_FILE, invalidate_cache

        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text("{}", encoding="utf-8")
        assert _CACHE_FILE.exists()

        invalidate_cache()
        assert not _CACHE_FILE.exists()


# ── manifest.py ───────────────────────────────────────────────────────────────

class TestManifest:
    """Tests for shibaclaw.updater.manifest."""

    SAMPLE_MANIFEST = {
        "version": "0.0.8",
        "from_version": "0.0.7",
        "release_notes": "Test release",
        "changes": [
            {"path": "shibaclaw/templates/USER.md", "overwrite": True, "note": "New section"},
            {"path": "shibaclaw/templates/SOUL.md", "overwrite": True},
            {"path": "shibaclaw/agent/loop.py", "overwrite": True},
        ],
    }

    def test_fetch_manifest(self):
        with patch("urllib.request.urlopen", return_value=_fake_urlopen(self.SAMPLE_MANIFEST)):
            from shibaclaw.updater.manifest import fetch_manifest
            manifest = fetch_manifest("https://example.com/manifest.json")

        assert manifest["version"] == "0.0.8"
        assert len(manifest["changes"]) == 3

    def test_personal_files_filtered(self):
        """Only template/skill SKILL.md files should be returned as personal."""
        from shibaclaw.updater.manifest import personal_files_in_manifest
        personal = personal_files_in_manifest(self.SAMPLE_MANIFEST)

        paths = [f["path"] for f in personal]
        assert "shibaclaw/templates/USER.md" in paths
        assert "shibaclaw/templates/SOUL.md" in paths
        # system file should NOT be in personal
        assert "shibaclaw/agent/loop.py" not in paths

    def test_skill_files_are_personal(self):
        """Skills SKILL.md files count as personal."""
        manifest = {
            "changes": [
                {"path": "shibaclaw/skills/github/SKILL.md", "overwrite": True},
                {"path": "shibaclaw/skills/github/scripts/run.sh", "overwrite": True},
            ]
        }
        from shibaclaw.updater.manifest import personal_files_in_manifest
        personal = personal_files_in_manifest(manifest)
        paths = [f["path"] for f in personal]
        assert "shibaclaw/skills/github/SKILL.md" in paths
        assert "shibaclaw/skills/github/scripts/run.sh" not in paths

    def test_empty_manifest(self):
        from shibaclaw.updater.manifest import personal_files_in_manifest
        assert personal_files_in_manifest({}) == []

