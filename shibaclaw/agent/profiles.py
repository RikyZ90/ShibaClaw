"""Agent profile management for session-level persona switching."""

import json
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_PROFILE_ID = "default"


class ProfileManager:
    """Manages agent profiles stored in workspace/profiles/.

    Each profile is a subdirectory containing a SOUL.md file.
    A manifest.json in the profiles root stores metadata (label, description, builtin).
    The 'default' profile uses the workspace root SOUL.md for backward compatibility.
    """

    MANIFEST_FILE = "manifest.json"

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.profiles_dir = workspace / "profiles"

    def _manifest_path(self) -> Path:
        return self.profiles_dir / self.MANIFEST_FILE

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        path = self._manifest_path()
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                logger.warning("Profiles manifest is not a dict, resetting")
                return {}
            return data
        except Exception:
            logger.warning("Failed to read profiles manifest")
            return {}

    def _save_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path().write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_soul_path(self, profile_id: str) -> Path:
        """Get the path to a profile's SOUL.md."""
        if profile_id == DEFAULT_PROFILE_ID:
            return self.workspace / "SOUL.md"
        return self.profiles_dir / profile_id / "SOUL.md"

    def get_soul_content(self, profile_id: str) -> str | None:
        """Get the SOUL.md content for a profile."""
        path = self.get_soul_path(profile_id)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all available profiles with metadata."""
        manifest = self._load_manifest()
        profiles: list[dict[str, Any]] = []

        # Always include default profile
        default_meta = manifest.get(DEFAULT_PROFILE_ID, {})
        entry: dict[str, Any] = {
            "id": DEFAULT_PROFILE_ID,
            "label": default_meta.get("label", "ShibaClaw"),
            "description": default_meta.get("description", "The original joyful Shiba assistant"),
            "builtin": True,
            "has_soul": (self.workspace / "SOUL.md").exists(),
        }
        if default_meta.get("avatar"):
            entry["avatar"] = default_meta["avatar"]
        profiles.append(entry)

        # Profiles from manifest
        for pid, meta in manifest.items():
            if pid == DEFAULT_PROFILE_ID:
                continue
            soul_path = self.profiles_dir / pid / "SOUL.md"
            entry = {
                "id": pid,
                "label": meta.get("label", pid),
                "description": meta.get("description", ""),
                "builtin": meta.get("builtin", False),
                "has_soul": soul_path.exists(),
            }
            if meta.get("avatar"):
                entry["avatar"] = meta["avatar"]
            profiles.append(entry)

        # Discover profiles not in manifest (user-created directories)
        known_ids = {p["id"] for p in profiles}
        if self.profiles_dir.exists():
            for d in sorted(self.profiles_dir.iterdir()):
                if d.is_dir() and d.name not in known_ids and (d / "SOUL.md").exists():
                    profiles.append(
                        {
                            "id": d.name,
                            "label": d.name.replace("-", " ").replace("_", " ").title(),
                            "description": "",
                            "builtin": False,
                            "has_soul": True,
                        }
                    )

        return profiles

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Get profile metadata + soul content."""
        manifest = self._load_manifest()
        meta = manifest.get(profile_id, {})

        if profile_id == DEFAULT_PROFILE_ID:
            result: dict[str, Any] = {
                "id": DEFAULT_PROFILE_ID,
                "label": meta.get("label", "ShibaClaw"),
                "description": meta.get("description", "The original joyful Shiba assistant"),
                "builtin": True,
                "soul": self.get_soul_content(DEFAULT_PROFILE_ID) or "",
            }
            if meta.get("avatar"):
                result["avatar"] = meta["avatar"]
            return result

        soul = self.get_soul_content(profile_id)
        if soul is None and not meta:
            return None
        result = {
            "id": profile_id,
            "label": meta.get("label", profile_id),
            "description": meta.get("description", ""),
            "builtin": meta.get("builtin", False),
            "soul": soul or "",
        }
        if meta.get("avatar"):
            result["avatar"] = meta["avatar"]
        return result

    def create_profile(
        self,
        profile_id: str,
        label: str,
        description: str = "",
        soul_content: str = "",
        avatar: str | None = None,
    ) -> dict[str, Any]:
        """Create a custom profile."""
        profile_dir = self.profiles_dir / profile_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "SOUL.md").write_text(soul_content, encoding="utf-8")

        manifest = self._load_manifest()
        entry: dict[str, Any] = {
            "label": label,
            "description": description,
            "builtin": False,
        }
        if avatar:
            entry["avatar"] = avatar
        manifest[profile_id] = entry
        self._save_manifest(manifest)
        return self.get_profile(profile_id)  # type: ignore[return-value]

    def update_profile(
        self,
        profile_id: str,
        label: str | None = None,
        description: str | None = None,
        soul_content: str | None = None,
        avatar: str | None = ...,
    ) -> dict[str, Any] | None:
        """Update profile metadata or soul content."""
        manifest = self._load_manifest()

        if profile_id == DEFAULT_PROFILE_ID:
            if soul_content is not None:
                (self.workspace / "SOUL.md").write_text(soul_content, encoding="utf-8")
            entry = manifest.get(
                DEFAULT_PROFILE_ID,
                {
                    "label": "ShibaClaw",
                    "description": "The original joyful Shiba assistant",
                    "builtin": True,
                },
            )
            if label is not None:
                entry["label"] = label
            if description is not None:
                entry["description"] = description
            if avatar is not ...:
                if avatar:
                    entry["avatar"] = avatar
                else:
                    entry.pop("avatar", None)
            manifest[DEFAULT_PROFILE_ID] = entry
            self._save_manifest(manifest)
            return self.get_profile(DEFAULT_PROFILE_ID)

        # Non-default profile
        if profile_id not in manifest:
            soul_path = self.profiles_dir / profile_id / "SOUL.md"
            if not soul_path.exists():
                return None

        if soul_content is not None:
            soul_path = self.profiles_dir / profile_id / "SOUL.md"
            soul_path.parent.mkdir(parents=True, exist_ok=True)
            soul_path.write_text(soul_content, encoding="utf-8")

        entry = manifest.get(profile_id, {})
        if label is not None:
            entry["label"] = label
        if description is not None:
            entry["description"] = description
        if avatar is not ...:
            if avatar:
                entry["avatar"] = avatar
            else:
                entry.pop("avatar", None)
        manifest[profile_id] = entry
        self._save_manifest(manifest)
        return self.get_profile(profile_id)

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a custom profile. Built-in and default profiles cannot be deleted."""
        manifest = self._load_manifest()
        meta = manifest.get(profile_id, {})
        if profile_id == DEFAULT_PROFILE_ID or meta.get("builtin"):
            return False

        profile_dir = self.profiles_dir / profile_id
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
        manifest.pop(profile_id, None)
        self._save_manifest(manifest)
        return True
