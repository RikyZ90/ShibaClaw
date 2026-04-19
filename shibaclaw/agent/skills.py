"""Skills loader for agent capabilities."""

import io
import json
import os
import re
import shutil
import zipfile
from pathlib import Path

# Default builtin skills directory (relative to this file)
BUILTIN_SKILLS_DIR = Path(__file__).parent.parent / "skills"


class SkillsLoader:
    """
    Loader for agent skills.

    Skills are markdown files (SKILL.md) that teach the agent how to use
    specific tools or perform certain tasks.
    """

    def __init__(self, workspace: Path, builtin_skills_dir: Path | None = None):
        self.workspace = workspace
        self.workspace_skills = workspace / "skills"
        self.builtin_skills = builtin_skills_dir or BUILTIN_SKILLS_DIR

    def list_skills(self, filter_unavailable: bool = True) -> list[dict[str, str]]:
        """
        List all available skills.

        Args:
            filter_unavailable: If True, filter out skills with unmet requirements.

        Returns:
            List of skill info dicts with 'name', 'path', 'source'.
        """
        skills = []

        # Workspace skills (highest priority)
        if self.workspace_skills.exists():
            for skill_dir in self.workspace_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skills.append(
                            {"name": skill_dir.name, "path": str(skill_file), "source": "workspace"}
                        )

        # Built-in skills
        if self.builtin_skills and self.builtin_skills.exists():
            for skill_dir in self.builtin_skills.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists() and not any(s["name"] == skill_dir.name for s in skills):
                        skills.append(
                            {"name": skill_dir.name, "path": str(skill_file), "source": "builtin"}
                        )

        # Filter by requirements
        if filter_unavailable:
            return [s for s in skills if self._check_requirements(self._get_skill_meta(s["name"]))]
        return skills

    def load_skill(self, name: str) -> str | None:
        """
        Load a skill by name.

        Args:
            name: Skill name (directory name).

        Returns:
            Skill content or None if not found.
        """
        # Check workspace first
        workspace_skill = self.workspace_skills / name / "SKILL.md"
        if workspace_skill.exists():
            return workspace_skill.read_text(encoding="utf-8")

        # Check built-in
        if self.builtin_skills:
            builtin_skill = self.builtin_skills / name / "SKILL.md"
            if builtin_skill.exists():
                return builtin_skill.read_text(encoding="utf-8")

        return None

    def load_skills_for_context(self, skill_names: list[str]) -> str:
        """
        Load specific skills for inclusion in agent context.

        Args:
            skill_names: List of skill names to load.

        Returns:
            Formatted skills content.
        """
        parts = []
        for name in skill_names:
            content = self.load_skill(name)
            if content:
                content = self._strip_frontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")

        return "\n\n---\n\n".join(parts) if parts else ""

    def build_skills_summary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).

        This is used for progressive loading - the agent can read the full
        skill content using read_file when needed.

        Returns:
            XML-formatted skills summary.
        """
        all_skills = self.list_skills(filter_unavailable=False)
        if not all_skills:
            return ""

        def escape_xml(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<skills>"]
        for s in all_skills:
            name = escape_xml(s["name"])
            path = s["path"]
            desc = escape_xml(self._get_skill_description(s["name"]))
            skill_meta = self._get_skill_meta(s["name"])
            available = self._check_requirements(skill_meta)

            lines.append(f'  <skill available="{str(available).lower()}">')
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")

            # Show missing requirements for unavailable skills
            if not available:
                missing = self._get_missing_requirements(skill_meta)
                if missing:
                    lines.append(f"    <requires>{escape_xml(missing)}</requires>")

            lines.append("  </skill>")
        lines.append("</skills>")

        return "\n".join(lines)

    def _get_missing_requirements(self, skill_meta: dict) -> str:
        """Get a description of missing requirements."""
        missing = []
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                missing.append(f"CLI: {b}")
        for env in requires.get("env", []):
            if not os.environ.get(env):
                missing.append(f"ENV: {env}")
        return ", ".join(missing)

    def _get_skill_description(self, name: str) -> str:
        """Get the description of a skill from its frontmatter."""
        meta = self.get_skill_metadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # Fallback to skill name

    def _strip_frontmatter(self, content: str) -> str:
        """Remove YAML frontmatter from markdown content."""
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end() :].strip()
        return content

    def _parse_shibaclaw_metadata(self, raw: str) -> dict:
        """Parse skill metadata JSON from frontmatter (supports shibaclaw and openclaw keys)."""
        try:
            data = json.loads(raw)
            return data.get("shibaclaw", data.get("openclaw", {})) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _check_requirements(self, skill_meta: dict) -> bool:
        """Check if skill requirements are met (bins, env vars)."""
        requires = skill_meta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True

    def _get_skill_meta(self, name: str) -> dict:
        """Get shibaclaw metadata for a skill (cached in frontmatter)."""
        meta = self.get_skill_metadata(name) or {}
        return self._parse_shibaclaw_metadata(meta.get("metadata", ""))

    @staticmethod
    def _extract_name_from_frontmatter(content: str) -> str | None:
        """Extract the 'name' field from YAML frontmatter."""
        if not content.startswith("---"):
            return None
        m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not m:
            return None
        for line in m.group(1).split("\n"):
            if line.startswith("name:"):
                val = line.split(":", 1)[1].strip().strip("\"'")
                if val:
                    return val
        return None

    def get_always_skills(self, pinned: list[str] | None = None) -> list[str]:
        """Get skills marked as always=true OR present in pinned list, that meet requirements."""
        result = []
        seen: set[str] = set()
        available = {s["name"] for s in self.list_skills(filter_unavailable=True)}

        # YAML always: true
        for s in self.list_skills(filter_unavailable=True):
            meta = self.get_skill_metadata(s["name"]) or {}
            skill_meta = self._parse_shibaclaw_metadata(meta.get("metadata", ""))
            if skill_meta.get("always") or meta.get("always"):
                if s["name"] not in seen:
                    result.append(s["name"])
                    seen.add(s["name"])

        # Config pinned skills
        for name in pinned or []:
            if name not in seen and name in available:
                result.append(name)
                seen.add(name)

        return result

    def delete_skill(self, name: str) -> bool:
        """Delete a workspace skill. Returns True on success. Refuses to delete built-in skills."""
        target = self.workspace_skills / name
        if not target.exists() or not target.is_dir():
            return False
        # Safety: must be inside workspace_skills
        try:
            target.resolve().relative_to(self.workspace_skills.resolve())
        except ValueError:
            return False
        shutil.rmtree(target)
        return True

    def import_skills_zip(
        self, zip_bytes: bytes, conflict: str = "skip", dry_run: bool = False
    ) -> dict:
        """Import SKILL.md folders from a zip archive into workspace/skills/.

        Args:
            zip_bytes: Raw zip file content.
            conflict: 'skip', 'overwrite', or 'rename'.
            dry_run: If True, only preview — don't write anything.

        Returns:
            Dict with imported/skipped counts and lists.
        """
        imported: list[str] = []
        skipped: list[str] = []

        with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
            skill_dirs: dict[str, str] = {}  # skill_name -> zip_prefix
            for info in zf.infolist():
                norm = info.filename.replace("\\", "/")
                basename = norm.rstrip("/").split("/")[-1]
                if basename.upper() != "SKILL.MD":
                    continue
                parts = norm.split("/")
                if len(parts) == 1:
                    # SKILL.md at root — derive name from frontmatter
                    raw = zf.read(info.filename).decode("utf-8", errors="replace")
                    sname = self._extract_name_from_frontmatter(raw) or "imported_skill"
                    skill_dirs.setdefault(sname, "")
                elif len(parts) >= 2:
                    skill_name = parts[-2]
                    prefix = "/".join(parts[:-1])
                    if skill_name:
                        skill_dirs.setdefault(skill_name, prefix)

            if not skill_dirs:
                return {
                    "imported": [],
                    "skipped": [],
                    "imported_count": 0,
                    "skipped_count": 0,
                    "error": "No SKILL.md folders found in archive",
                }

            self.workspace_skills.mkdir(parents=True, exist_ok=True)

            for skill_name, prefix in skill_dirs.items():
                dest = self.workspace_skills / skill_name
                if dest.exists():
                    if conflict == "skip":
                        skipped.append(skill_name)
                        continue
                    elif conflict == "rename":
                        n = 2
                        while (self.workspace_skills / f"{skill_name}_{n}").exists():
                            n += 1
                        skill_name_final = f"{skill_name}_{n}"
                        dest = self.workspace_skills / skill_name_final
                    elif conflict == "overwrite":
                        if not dry_run:
                            shutil.rmtree(dest)
                    else:
                        skipped.append(skill_name)
                        continue
                else:
                    skill_name_final = skill_name  # noqa: F841

                if not dry_run:
                    dest.mkdir(parents=True, exist_ok=True)
                    for info in zf.infolist():
                        zpath = info.filename.replace("\\", "/")
                        if info.is_dir():
                            continue
                        if prefix == "":
                            rel = zpath
                        elif zpath.startswith(prefix + "/"):
                            rel = zpath[len(prefix) + 1 :]
                        else:
                            continue
                        target_file = dest / rel
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        target_file.write_bytes(zf.read(info.filename))

                imported.append(skill_name)

        return {
            "imported": imported,
            "skipped": skipped,
            "imported_count": len(imported),
            "skipped_count": len(skipped),
        }

    def get_skill_metadata(self, name: str) -> dict | None:
        """
        Get metadata from a skill's frontmatter.

        Args:
            name: Skill name.

        Returns:
            Metadata dict or None.
        """
        content = self.load_skill(name)
        if not content:
            return None

        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                raw_yaml = match.group(1)
                # Try proper YAML parsing first, fall back to simple split
                try:
                    import yaml

                    parsed = yaml.safe_load(raw_yaml)
                    if isinstance(parsed, dict):
                        # Stringify values for backward compatibility
                        return {k: str(v) if v is not None else "" for k, v in parsed.items()}
                except Exception:
                    pass
                # Fallback: simple line-by-line parsing
                metadata = {}
                for line in raw_yaml.split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip("\"'")
                return metadata

        return None
