from pathlib import Path


def _make_source_tree(root: Path) -> None:
    (root / "shibaclaw").mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text('[project]\nname = "shibaclaw"\n', encoding="utf-8")
    (root / "README.md").write_text("# ShibaClaw\n", encoding="utf-8")
    (root / "shibaclaw" / "__init__.py").write_text("__version__ = '0.0.0'\n", encoding="utf-8")


def test_detector_prefers_source_checkout_over_venv(tmp_path, monkeypatch):
    from shibaclaw.updater import detector

    _make_source_tree(tmp_path)
    monkeypatch.setattr(detector, "get_runtime_root_path", lambda: tmp_path)
    monkeypatch.setattr(detector, "is_running_as_exe", lambda: False)
    monkeypatch.setattr(detector, "is_running_in_docker", lambda: False)
    monkeypatch.setattr(detector, "_has_installed_distribution", lambda: True)
    monkeypatch.setattr(detector, "_system_installation_method", lambda: "pip")

    assert detector.get_installation_method() == "source"


def test_detector_recognizes_pip_install_without_source_tree(tmp_path, monkeypatch):
    from shibaclaw.updater import detector

    monkeypatch.setattr(detector, "get_runtime_root_path", lambda: tmp_path)
    monkeypatch.setattr(detector, "is_running_as_exe", lambda: False)
    monkeypatch.setattr(detector, "is_running_in_docker", lambda: False)
    monkeypatch.setattr(detector, "_has_installed_distribution", lambda: True)
    monkeypatch.setattr(detector, "_system_installation_method", lambda: "source")

    assert detector.get_installation_method() == "pip"


def test_detector_accepts_official_remote_urls(monkeypatch):
    from shibaclaw.updater import detector

    monkeypatch.setattr(
        detector,
        "get_git_remote_url",
        lambda root=None: "git@github.com:RikyZ90/ShibaClaw.git",
    )

    assert detector.is_official_repo_checkout() is True


def test_runtime_metadata_exposes_detection_fields(tmp_path, monkeypatch):
    from shibaclaw.updater import detector

    _make_source_tree(tmp_path)
    monkeypatch.setattr(detector, "get_runtime_root_path", lambda: tmp_path)
    monkeypatch.setattr(detector, "get_current_version", lambda: "0.3.7")
    monkeypatch.setattr(detector, "get_installation_method", lambda: "source")
    monkeypatch.setattr(detector, "get_git_remote_url", lambda root=None: "https://github.com/RikyZ90/ShibaClaw.git")
    monkeypatch.setattr(detector, "is_running_as_exe", lambda: False)

    metadata = detector.get_runtime_metadata()

    assert metadata["install_method"] == "source"
    assert metadata["current_version"] == "0.3.7"
    assert metadata["runtime_root"] == str(tmp_path)
    assert metadata["is_official_checkout"] is True