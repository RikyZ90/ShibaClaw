import sys


def test_version_prefers_pyproject_for_source_checkout(tmp_path, monkeypatch):
    import shibaclaw

    repo_root = tmp_path / "repo"
    package_dir = repo_root / "shibaclaw"
    package_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / "README.md").write_text("# ShibaClaw\n", encoding="utf-8")
    (repo_root / "pyproject.toml").write_text(
        '[project]\nname = "shibaclaw"\nversion = "1.2.3"\n',
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    monkeypatch.setattr(shibaclaw, "__file__", str(package_dir / "__init__.py"))
    monkeypatch.setattr("importlib.metadata.version", lambda name: "9.9.9")
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert shibaclaw._get_version() == "1.2.3"



def test_version_prefers_installed_metadata_over_packaged_manifest(tmp_path, monkeypatch):
    import shibaclaw

    package_dir = tmp_path / "site-packages" / "shibaclaw"
    (package_dir / "updater").mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "updater" / "update_manifest.json").write_text(
        '{"version": "0.2.1"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(shibaclaw, "__file__", str(package_dir / "__init__.py"))
    monkeypatch.setattr("importlib.metadata.version", lambda name: "0.3.8")
    monkeypatch.delattr(sys, "frozen", raising=False)

    assert shibaclaw._get_version() == "0.3.8"


def test_version_prefers_manifest_for_frozen_bundle(tmp_path, monkeypatch):
    import shibaclaw

    package_dir = tmp_path / "bundle" / "shibaclaw"
    (package_dir / "updater").mkdir(parents=True, exist_ok=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "updater" / "update_manifest.json").write_text(
        '{"version": "0.4.0"}',
        encoding="utf-8",
    )

    monkeypatch.setattr(shibaclaw, "__file__", str(package_dir / "__init__.py"))
    monkeypatch.setattr("importlib.metadata.version", lambda name: "0.3.8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert shibaclaw._get_version() == "0.4.0"
