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
