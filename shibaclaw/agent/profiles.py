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

    def get_disabled_tools(self, profile_id: str | None) -> list[str]:
        """Return disabled tool names for *profile_id* ("*" means all tools)."""
        pid = profile_id or DEFAULT_PROFILE_ID
        meta = self._load_manifest().get(pid, {})
        disabled = meta.get("disabled_tools")
        if not isinstance(disabled, list):
            return []
        return [str(x) for x in disabled]

    def get_enabled_tools(self, profile_id: str | None) -> list[str] | None:
        """Return enabled tool allowlist for *profile_id*, or None if unrestricted."""
        pid = profile_id or DEFAULT_PROFILE_ID
        meta = self._load_manifest().get(pid, {})
        enabled = meta.get("enabled_tools")
        if not isinstance(enabled, list):
            return None
        return [str(x) for x in enabled]

    def get_temperature(self, profile_id: str | None) -> float | None:
        """Return profile temperature override, or None for global default."""
        pid = profile_id or DEFAULT_PROFILE_ID
        meta = self._load_manifest().get(pid, {})
        temp = meta.get("temperature")
        if temp is None:
            return None
        try:
            return float(temp)
        except (TypeError, ValueError):
            return None

    def get_allowed_models(self, profile_id: str | None) -> list[str] | None:
        """Return model allowlist for *profile_id*, or None if unrestricted.

        Distinguishes missing key (None = unrestricted) from empty list
        (``[]`` = deny all models).
        """
        pid = profile_id or DEFAULT_PROFILE_ID
        meta = self._load_manifest().get(pid, {})
        if "allowed_models" not in meta:
            return None
        allowed = meta.get("allowed_models")
        if not isinstance(allowed, list):
            return None
        return [str(x).strip() for x in allowed if str(x).strip()]

    def model_allowed(self, profile_id: str | None, model: str | None) -> bool:
        """True if model is permitted for profile.

        Matching: exact (case-insensitive) or ``fnmatch`` wildcards
        (e.g. ``openai/*``). Substring matching is intentionally not used.
        ``None`` allowlist = unrestricted; ``[]`` = deny all.
        """
        import fnmatch

        if not model:
            return True
        allowed = self.get_allowed_models(profile_id)
        if allowed is None:
            return True
        if not allowed:
            return False
        m = model.strip().lower()
        for entry in allowed:
            e = entry.strip().lower()
            if not e:
                continue
            if m == e or fnmatch.fnmatch(m, e):
                return True
            # Also allow matching bare model id against provider/model entries.
            if "/" in m and fnmatch.fnmatch(m.split("/", 1)[1], e):
                return True
        return False

    def get_default_knowledge_bases(self, profile_id: str | None) -> list[str]:
        """Return default Knowledge Base collection ids for *profile_id*."""
        pid = profile_id or DEFAULT_PROFILE_ID
        meta = self._load_manifest().get(pid, {})
        kbs = meta.get("knowledge_bases")
        if not isinstance(kbs, list):
            return []
        return [str(x) for x in kbs]

    def sync_session_knowledge_bases(
        self,
        metadata: dict,
        new_profile_id: str | None,
        old_profile_id: str | None = None,
    ) -> bool:
        """Pin/unpin profile default KBs on profile switch. Returns True if changed."""
        new_defaults = self.get_default_knowledge_bases(new_profile_id)
        old_defaults = (
            self.get_default_knowledge_bases(old_profile_id) if old_profile_id is not None else []
        )
        current = metadata.get("knowledge_bases")
        if not isinstance(current, list):
            current = []
        else:
            current = [str(x) for x in current]

        changed = False
        if old_defaults:
            filtered = [x for x in current if x not in set(old_defaults)]
            if filtered != current:
                current = filtered
                changed = True
        for kb_id in new_defaults:
            if kb_id not in current:
                current.append(kb_id)
                changed = True
        if changed:
            metadata["knowledge_bases"] = current
        return changed

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
        if "pinned_skills" in default_meta:
            entry["pinned_skills"] = default_meta["pinned_skills"]
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
            if "pinned_skills" in meta:
                entry["pinned_skills"] = meta["pinned_skills"]
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
            if "pinned_skills" in meta:
                result["pinned_skills"] = meta["pinned_skills"]
            if "disabled_tools" in meta:
                result["disabled_tools"] = meta["disabled_tools"]
            if "enabled_tools" in meta:
                result["enabled_tools"] = meta["enabled_tools"]
            if "temperature" in meta:
                result["temperature"] = meta["temperature"]
            if "knowledge_bases" in meta:
                result["knowledge_bases"] = meta["knowledge_bases"]
            if "allowed_models" in meta:
                result["allowed_models"] = meta["allowed_models"]
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
        if "pinned_skills" in meta:
            result["pinned_skills"] = meta["pinned_skills"]
        if "disabled_tools" in meta:
            result["disabled_tools"] = meta["disabled_tools"]
        if "enabled_tools" in meta:
            result["enabled_tools"] = meta["enabled_tools"]
        if "temperature" in meta:
            result["temperature"] = meta["temperature"]
        if "knowledge_bases" in meta:
            result["knowledge_bases"] = meta["knowledge_bases"]
        if "allowed_models" in meta:
            result["allowed_models"] = meta["allowed_models"]
        return result

    def create_profile(
        self,
        profile_id: str,
        label: str,
        description: str = "",
        soul_content: str = "",
        avatar: str | None = None,
        pinned_skills: list[str] | None = None,
        disabled_tools: list[str] | None = None,
        enabled_tools: list[str] | None = None,
        temperature: float | None = None,
        knowledge_bases: list[str] | None = None,
        allowed_models: list[str] | None = None,
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
        if pinned_skills is not None:
            entry["pinned_skills"] = pinned_skills
        if disabled_tools is not None:
            entry["disabled_tools"] = disabled_tools
        if enabled_tools is not None:
            entry["enabled_tools"] = enabled_tools
        if temperature is not None:
            entry["temperature"] = temperature
        if knowledge_bases is not None:
            entry["knowledge_bases"] = knowledge_bases
        if allowed_models is not None:
            entry["allowed_models"] = allowed_models
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
        pinned_skills: list[str] | None = ...,
        disabled_tools: list[str] | None = ...,
        enabled_tools: list[str] | None = ...,
        temperature: float | None = ...,
        knowledge_bases: list[str] | None = ...,
        allowed_models: list[str] | None = ...,
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
            if pinned_skills is not ...:
                if pinned_skills is not None:
                    entry["pinned_skills"] = pinned_skills
                else:
                    entry.pop("pinned_skills", None)
            for field, value in (
                ("disabled_tools", disabled_tools),
                ("enabled_tools", enabled_tools),
                ("temperature", temperature),
                ("knowledge_bases", knowledge_bases),
                ("allowed_models", allowed_models),
            ):
                if value is not ...:
                    if value is None:
                        entry.pop(field, None)
                    else:
                        entry[field] = value
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
        if pinned_skills is not ...:
            if pinned_skills is not None:
                entry["pinned_skills"] = pinned_skills
            else:
                entry.pop("pinned_skills", None)
        for field, value in (
            ("disabled_tools", disabled_tools),
            ("enabled_tools", enabled_tools),
            ("temperature", temperature),
            ("knowledge_bases", knowledge_bases),
            ("allowed_models", allowed_models),
        ):
            if value is not ...:
                if value is None:
                    entry.pop(field, None)
                else:
                    entry[field] = value
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
