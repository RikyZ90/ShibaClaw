from pathlib import Path


def test_apply_update_returns_manual_report_for_docker(tmp_path):
    from shibaclaw.updater.apply import apply_update

    report = apply_update(
        {
            "install_method": "docker",
            "latest": "0.3.8",
            "action_kind": "manual-command",
            "action_label": "Pull latest image",
            "action_command": "docker pull rikyz90/shibaclaw:latest",
        },
        tmp_path,
    )

    assert report["requires_manual_action"] is True
    assert report["restarting"] is False
    assert report["pip"] is None
    assert "docker pull" in report["message"]


def test_apply_update_runs_backup_and_pip_for_pip(tmp_path, monkeypatch):
    from shibaclaw.updater import apply

    personal_file = tmp_path / "USER.md"
    personal_file.write_text("customized\n", encoding="utf-8")
    manifest = {
        "version": "0.3.8",
        "changes": [
            {"path": "USER.md", "overwrite": False},
            {"path": "skills/memory/SKILL.md", "overwrite": True},
        ],
    }
    monkeypatch.setattr(apply, "_pip_upgrade", lambda version: {"ok": True, "output": f"updated {version}"})

    report = apply.apply_update(
        {"install_method": "pip", "latest": "0.3.8", "action_kind": "automatic"},
        tmp_path,
        manifest=manifest,
    )

    assert report["requires_manual_action"] is False
    assert report["pip"]["ok"] is True
    assert report["backup"]["moved"]
    backup_target = Path(report["backup"]["moved"][0]["to"])
    assert backup_target.exists()
    assert backup_target.read_text(encoding="utf-8") == "customized\n"


def test_apply_update_supports_manifest_only_payload(tmp_path, monkeypatch):
    from shibaclaw.updater import apply

    monkeypatch.setattr(apply, "get_installation_method", lambda: "pip")
    monkeypatch.setattr(apply, "_pip_upgrade", lambda version: {"ok": True, "output": version})

    report = apply.apply_update(None, tmp_path, manifest={"version": "0.3.9", "changes": []})

    assert report["version"] == "0.3.9"
    assert report["pip"]["output"] == "0.3.9"


def test_apply_update_runs_exe_for_exe(tmp_path, monkeypatch):
    from shibaclaw.updater import apply

    monkeypatch.setattr(
        apply,
        "_exe_upgrade",
        lambda version, download_url, progress_cb=None: {
            "ok": True,
            "output": f"updated {version} via {download_url}",
        },
    )

    report = apply.apply_update(
        {
            "install_method": "exe",
            "latest": "0.3.8",
            "action_kind": "automatic",
            "action_url": "https://example.com/ShibaClaw.zip",
        },
        tmp_path,
        manifest={"version": "0.3.8", "changes": []},
    )

    assert report["requires_manual_action"] is False
    assert report["exe"]["ok"] is True
    assert "https://example.com/ShibaClaw.zip" in report["exe"]["output"]


def test_exe_upgrade_downloads_and_launches(tmp_path, monkeypatch):
    import sys
    from shibaclaw.updater import apply

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    bundled_dir = tmp_path / "scripts" / "install"
    bundled_dir.mkdir(parents=True)
    bundled_ps1 = bundled_dir / "install.ps1"
    bundled_ps1.write_text("param($Version, $InstallDir, $LocalZipPath)\n", encoding="utf-8")

    class MockResponse:
        def __init__(self, content):
            self.content = content
            self.text = content.decode("utf-8")
            self.headers = {"content-length": str(len(content))}
        def raise_for_status(self):
            pass
        def iter_bytes(self, chunk_size=8192):
            yield self.content

    class MockStreamContext:
        def __init__(self, response):
            self.response = response
        def __enter__(self):
            return self.response
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockClient:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
        def get(self, url):
            return MockResponse(b"mock_ps1_script")
        def stream(self, method, url):
            return MockStreamContext(MockResponse(b"mock_zip_content"))

    import httpx
    monkeypatch.setattr(httpx, "Client", lambda *args, **kwargs: MockClient())

    launched_cmd = []
    class MockPopen:
        def __init__(self, cmd, **kwargs):
            nonlocal launched_cmd
            launched_cmd = cmd

    import subprocess
    monkeypatch.setattr(subprocess, "Popen", MockPopen)

    progress_calls = []
    def progress_cb(current, total):
        progress_calls.append((current, total))

    res = apply._exe_upgrade(
        version="0.3.8",
        download_url="https://example.com/ShibaClaw.zip",
        progress_cb=progress_cb
    )

    assert res["ok"] is True
    assert "launched successfully" in res["output"]
    assert len(progress_calls) > 0
    assert progress_calls[-1][0] == progress_calls[-1][1]
    assert "-LocalZipPath" in launched_cmd

