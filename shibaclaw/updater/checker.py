"""Check remote sources for a newer ShibaClaw update."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from shibaclaw.config.paths import get_app_root
from shibaclaw.helpers.system import InstallMethod
from shibaclaw.updater.detector import (
    DOCKER_IMAGE,
    GITHUB_REPO,
    GITHUB_REPO_URL,
    PYPI_PACKAGE,
    UPDATE_MANIFEST_ASSET,
    WINDOWS_RELEASE_ASSET,
    get_current_version,
    get_installation_method,
    get_runtime_root_path,
    is_official_repo_checkout,
)
from shibaclaw.updater.manifest import fetch_manifest

_CACHE_TTL = 1800
_CACHE_FILE = get_app_root() / "update_cache.json"
_GITHUB_RELEASES_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
_PYPI_JSON_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
_DOCKER_TAGS_URL = "https://hub.docker.com/v2/namespaces/rikyz90/repositories/shibaclaw/tags?page_size=100"
_REQUEST_TIMEOUT = 8.0
_REQUEST_RETRIES = 3
_VERSION_RE = re.compile(
    r"^v?(?P<numeric>\d+(?:\.\d+)*)\s*(?P<pre>a|alpha|b|beta|rc)?(?P<pre_num>\d*)$",
    re.IGNORECASE,
)
_DEFAULT_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": f"ShibaClaw/{get_current_version()}",
}


def _cache_key(install_method: InstallMethod, current_version: str) -> str:
    return f"{install_method}:{current_version}"


def _blank_result(install_method: InstallMethod, current: str) -> dict[str, Any]:
    action_defaults: dict[InstallMethod, dict[str, Any]] = {
        "pip": {
            "action_kind": "automatic",
            "action_label": "Update now",
            "action_command": f"pip install --upgrade {PYPI_PACKAGE}",
            "action_url": f"https://pypi.org/project/{PYPI_PACKAGE}/",
            "notes": [],
        },
        "docker": {
            "action_kind": "manual-command",
            "action_label": "Pull latest image",
            "action_command": f"docker pull {DOCKER_IMAGE}:latest",
            "action_url": f"{GITHUB_REPO_URL}/blob/main/deploy_guide.md",
            "notes": [
                "If you run ShibaClaw with docker compose, recreate the service after pulling the new image.",
            ],
        },
        "exe": {
            "action_kind": "manual-download",
            "action_label": "Download Windows build",
            "action_command": None,
            "action_url": f"{GITHUB_REPO_URL}/releases/latest",
            "notes": [
                "Windows desktop builds must be replaced manually after download.",
            ],
        },
        "source": {
            "action_kind": "manual-command",
            "action_label": "Pull latest source",
            "action_command": "git pull --ff-only && pip install -e .",
            "action_url": GITHUB_REPO_URL,
            "notes": [
                "Source checkouts are updated manually so local changes stay under your control.",
            ],
        },
    }
    base = action_defaults[install_method]
    return {
        "install_method": install_method,
        "current": current,
        "latest": current,
        "display_current": current,
        "display_latest": current,
        "update_available": False,
        "action_kind": base["action_kind"],
        "action_label": base["action_label"],
        "action_command": base["action_command"],
        "action_url": base["action_url"],
        "release_url": None,
        "download_url": None,
        "manifest_url": None,
        "notification": None,
        "checked_at": int(time.time()),
        "error": None,
        "stale": False,
        "summary": "You're up to date.",
        "notes": list(base["notes"]),
    }


def _version_key(value: str) -> tuple[tuple[int, ...], int, int]:
    text = (value or "").strip().lstrip("v")
    match = _VERSION_RE.match(text)
    if match:
        numeric = tuple(int(part) for part in match.group("numeric").split("."))
        pre = (match.group("pre") or "").lower()
        pre_num = int(match.group("pre_num") or 0)
        order = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "rc": 2}
        return numeric, order.get(pre, 3), pre_num
    numeric = tuple(int(part) for part in re.findall(r"\d+", text))
    return numeric or (0,), 3, 0


def _release_url_for(version: str) -> str:
    clean = (version or "").strip().lstrip("v")
    return f"https://github.com/{GITHUB_REPO}/releases/tag/v{clean}"


def _manifest_url_for(version: str) -> str:
    clean = (version or "").strip().lstrip("v")
    return f"https://github.com/{GITHUB_REPO}/releases/download/v{clean}/{UPDATE_MANIFEST_ASSET}"


def _windows_download_url_for(version: str) -> str:
    clean = (version or "").strip().lstrip("v")
    return f"https://github.com/{GITHUB_REPO}/releases/download/v{clean}/{WINDOWS_RELEASE_ASSET}"


def _latest_release_info() -> dict[str, Any]:
    data = _request_json(_GITHUB_RELEASES_LATEST_URL)
    tagged_version = (data.get("tag_name") or "").lstrip("v")
    assets = data.get("assets", [])

    manifest_url = next(
        (
            asset.get("browser_download_url")
            for asset in assets
            if asset.get("name") == UPDATE_MANIFEST_ASSET
        ),
        _manifest_url_for(tagged_version) if tagged_version else None,
    )
    manifest = None
    manifest_error = None
    if manifest_url:
        try:
            manifest = fetch_manifest(manifest_url)
        except Exception as exc:
            manifest_error = str(exc)

    latest = (manifest or {}).get("version") or tagged_version
    if not latest:
        raise RuntimeError("Latest GitHub release does not expose a usable version")

    download_url = next(
        (
            asset.get("browser_download_url")
            for asset in assets
            if asset.get("name") == WINDOWS_RELEASE_ASSET
        ),
        _windows_download_url_for(tagged_version or latest),
    )

    return {
        "latest": latest,
        "tagged_version": tagged_version or latest,
        "release_url": data.get("html_url") or _release_url_for(latest),
        "manifest_url": manifest_url,
        "download_url": download_url,
        "manifest": manifest,
        "manifest_error": manifest_error,
    }


def _load_cache_state() -> dict[str, Any]:
    try:
        if not _CACHE_FILE.exists():
            return {"entries": {}, "last_success": {}}
        data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        if "entries" in data:
            data.setdefault("last_success", {})
            return data
        if isinstance(data, dict) and "current" in data:
            current = data.get("current") or get_current_version()
            install_method = data.get("install_method") or get_installation_method()
            key = _cache_key(install_method, current)
            last_success = {} if data.get("error") else {key: data}
            return {"entries": {key: data}, "last_success": last_success}
    except Exception:
        pass
    return {"entries": {}, "last_success": {}}


def _save_cache_state(state: dict[str, Any]) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(state), encoding="utf-8")
    except Exception:
        pass


def _load_cached_result(
    install_method: InstallMethod,
    current_version: str,
    *,
    fresh_only: bool,
) -> dict[str, Any] | None:
    key = _cache_key(install_method, current_version)
    state = _load_cache_state()
    candidate = None

    if fresh_only:
        candidate = state.get("entries", {}).get(key)
        if not candidate:
            return None
        if time.time() - candidate.get("checked_at", 0) >= _CACHE_TTL:
            return None
    else:
        candidate = state.get("last_success", {}).get(key) or state.get("entries", {}).get(key)
        if not candidate:
            return None

    return dict(candidate)


def _save_cached_result(result: dict[str, Any]) -> None:
    key = _cache_key(result["install_method"], result["current"])
    state = _load_cache_state()
    state.setdefault("entries", {})[key] = result
    if not result.get("error"):
        state.setdefault("last_success", {})[key] = result
    _save_cache_state(state)


def _request_json(url: str, *, timeout: float = _REQUEST_TIMEOUT) -> Any:
    last_error: Exception | None = None
    for attempt in range(_REQUEST_RETRIES):
        try:
            with httpx.Client(
                headers=_DEFAULT_HEADERS,
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()
        except (ValueError, httpx.HTTPError) as exc:
            last_error = exc
            if attempt + 1 >= _REQUEST_RETRIES:
                break
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(str(last_error or "Unknown network error"))


def _action_target(result: dict[str, Any]) -> str | None:
    return result.get("action_command") or result.get("action_url") or result.get("release_url")


def _build_notification(result: dict[str, Any]) -> dict[str, Any] | None:
    if not result.get("update_available"):
        return None

    action_target = _action_target(result)
    lines = [
        "🆕 *ShibaClaw update available*",
        f"{result.get('display_current') or result.get('current')} → {result.get('display_latest') or result.get('latest')}",
    ]
    if action_target:
        lines.append(f"Suggested: {action_target}")
    elif result.get("summary"):
        lines.append(result["summary"])

    return {
        "category": "update",
        "title": "ShibaClaw update available",
        "body": result.get("summary") or "A newer ShibaClaw update is available.",
        "install_method": result.get("install_method"),
        "current": result.get("current"),
        "latest": result.get("latest"),
        "display_current": result.get("display_current"),
        "display_latest": result.get("display_latest"),
        "action_label": result.get("action_label"),
        "action_command": result.get("action_command"),
        "action_url": result.get("action_url") or result.get("release_url"),
        "text": "\n".join(lines).strip(),
    }


def _finalize_result(result: dict[str, Any]) -> dict[str, Any]:
    result["checked_at"] = int(time.time())
    result["notification"] = _build_notification(result)
    return result


def _check_pip(current: str) -> dict[str, Any]:
    result = _blank_result("pip", current)
    data = _request_json(_PYPI_JSON_URL)
    latest = (data.get("info") or {}).get("version") or current

    result["latest"] = latest
    result["display_latest"] = latest
    result["release_url"] = _release_url_for(latest)
    result["manifest_url"] = _manifest_url_for(latest)
    result["action_url"] = result["release_url"]
    result["update_available"] = _version_key(latest) > _version_key(current)
    result["summary"] = (
        f"Version {latest} is available on PyPI."
        if result["update_available"]
        else f"PyPI is already on version {current}."
    )
    return _finalize_result(result)


def _iter_docker_semver_tags() -> list[str]:
    tags: list[str] = []
    next_url = _DOCKER_TAGS_URL
    page_count = 0

    while next_url and page_count < 5:
        payload = _request_json(next_url)
        for item in payload.get("results", []):
            name = (item.get("name") or "").strip()
            if _VERSION_RE.match(name.lstrip("v")):
                tags.append(name.lstrip("v"))
        next_url = payload.get("next")
        page_count += 1

    if not tags:
        raise RuntimeError("No semver Docker tags found on Docker Hub")
    return tags


def _check_docker(current: str) -> dict[str, Any]:
    result = _blank_result("docker", current)
    latest = max(_iter_docker_semver_tags(), key=_version_key)

    result["latest"] = latest
    result["display_latest"] = latest
    result["release_url"] = _release_url_for(latest)
    result["manifest_url"] = _manifest_url_for(latest)
    result["update_available"] = _version_key(latest) > _version_key(current)
    result["summary"] = (
        f"Docker image tag {latest} is available."
        if result["update_available"]
        else f"Docker Hub already exposes tag {current} as the latest semver release."
    )
    return _finalize_result(result)


def _check_exe(current: str) -> dict[str, Any]:
    result = _blank_result("exe", current)
    release = _latest_release_info()
    latest = release["latest"]

    result["latest"] = latest
    result["display_latest"] = latest
    result["download_url"] = release["download_url"]
    result["release_url"] = release["release_url"]
    result["action_url"] = release["download_url"] or result["release_url"]
    result["manifest_url"] = release["manifest_url"]
    result["update_available"] = _version_key(latest) > _version_key(current)
    result["summary"] = (
        f"Windows desktop build {latest} is available."
        if result["update_available"]
        else f"The current Windows build already matches release {current}."
    )
    if release.get("manifest_error"):
        result["notes"].append(
            "Release manifest could not be read; the latest GitHub release tag was used as a fallback."
        )
    return _finalize_result(result)


def _check_source(current: str) -> dict[str, Any]:
    result = _blank_result("source", current)
    runtime_root = get_runtime_root_path()
    result["release_url"] = f"{GITHUB_REPO_URL}/releases/latest"

    if not is_official_repo_checkout(runtime_root):
        result["summary"] = (
            "Source checkout detected. Automatic release-manifest checks are limited to the official repository."
        )
        result["notes"].append(
            "Use git pull in your checkout, then reinstall with pip install -e . when needed."
        )
        return _finalize_result(result)

    release = _latest_release_info()
    latest = release["latest"]
    current_key = _version_key(current)
    latest_key = _version_key(latest)

    result["latest"] = latest
    result["display_latest"] = latest
    result["release_url"] = release["release_url"]
    result["manifest_url"] = release["manifest_url"]
    result["action_url"] = release["release_url"]

    if latest_key > current_key:
        result["update_available"] = True
        result["action_label"] = "Checkout release tag"
        result["action_command"] = f"git fetch --tags && git checkout v{latest} && pip install -e ."
        result["summary"] = f"Release manifest {latest} is available for this source checkout."
    elif latest_key == current_key:
        result["action_label"] = "View release"
        result["action_command"] = None
        result["summary"] = f"This source checkout already matches released version {current}."
    else:
        result["action_label"] = "View release"
        result["action_command"] = None
        result["summary"] = (
            f"This source checkout reports version {current}, which is newer than the latest released manifest {latest}."
        )
        result["notes"].append(
            "If you are intentionally tracking unreleased commits, no action is required."
        )

    if release.get("manifest_error"):
        result["notes"].append(
            "Release manifest could not be read; the latest GitHub release tag was used as a fallback."
        )
    return _finalize_result(result)


def check_for_update(
    force: bool = False,
    installation_method: InstallMethod | None = None,
) -> dict[str, Any]:
    """Check for updates based on the detected installation method."""
    current = get_current_version()
    method = installation_method or get_installation_method()

    if not force:
        cached = _load_cached_result(method, current, fresh_only=True)
        if cached:
            return cached

    stale = _load_cached_result(method, current, fresh_only=False)
    handlers = {
        "pip": _check_pip,
        "docker": _check_docker,
        "exe": _check_exe,
        "source": _check_source,
    }

    try:
        result = handlers[method](current)
    except Exception as exc:
        if stale:
            stale["stale"] = True
            stale["error"] = f"Using cached update result after refresh failed: {exc}"
            return stale
        result = _blank_result(method, current)
        result["summary"] = "Unable to complete the update check."
        result["error"] = str(exc)
        result = _finalize_result(result)

    _save_cached_result(result)
    return result


def invalidate_cache() -> None:
    try:
        if _CACHE_FILE.exists():
            _CACHE_FILE.unlink()
    except Exception:
        pass
