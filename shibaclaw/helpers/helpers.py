"""Helper functions for the ShibaClaw ecosystem."""

import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import tiktoken


def detect_image_mime(data: bytes) -> str | None:
    """Detect image MIME type from magic bytes, ignoring file extension."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def timestamp() -> str:
    """Current ISO timestamp."""
    return datetime.now().isoformat()


def current_time_str() -> str:
    """Human-readable current time with weekday and timezone, e.g. '2026-03-15 22:30 (Saturday) (CST)'."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    tz = time.strftime("%Z") or "UTC"
    return f"{now} ({tz})"


_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*]')

def safe_filename(name: str) -> str:
    """Replace unsafe path characters with underscores."""
    return _UNSAFE_CHARS.sub("_", name).strip()


def split_message(content: str, max_len: int = 2000) -> list[str]:
    """
    Split content into chunks within max_len, preferring line breaks.

    Args:
        content: The text content to split.
        max_len: Maximum length per chunk (default 2000 for Discord compatibility).

    Returns:
        List of message chunks, each within max_len.
    """
    if not content:
        return []
    if len(content) <= max_len:
        return [content]
    chunks: list[str] = []
    while content:
        if len(content) <= max_len:
            chunks.append(content)
            break
        cut = content[:max_len]
        # Try to break at newline first, then space, then hard break
        pos = cut.rfind('\n')
        if pos <= 0:
            pos = cut.rfind(' ')
        if pos <= 0:
            pos = max_len
        chunks.append(content[:pos])
        content = content[pos:].lstrip()
    return chunks


def _sync_builtin_skills_to_workspace(workspace: Path, silent: bool = False) -> list[str]:
    """Copy builtin skills into workspace/skills.

    New skills are copied automatically. Existing skills are overwritten
    only after the user confirms (unless *silent* mode is active, in which
    case existing skills are left untouched).
    """
    from shibaclaw.agent.skills import BUILTIN_SKILLS_DIR

    workspace_skills_dir = workspace / "skills"
    workspace_skills_dir.mkdir(parents=True, exist_ok=True)

    if not BUILTIN_SKILLS_DIR.exists():
        return []

    new_skills: list[Path] = []
    existing_skills: list[Path] = []

    for skill_dir in BUILTIN_SKILLS_DIR.iterdir():
        if not skill_dir.is_dir():
            continue
        dst = workspace_skills_dir / skill_dir.name
        if dst.exists():
            existing_skills.append(skill_dir)
        else:
            new_skills.append(skill_dir)

    copied = []

    # New skills — copy without asking
    for skill_dir in new_skills:
        dst = workspace_skills_dir / skill_dir.name
        shutil.copytree(skill_dir, dst)
        copied.append(skill_dir.name)

    # Existing skills — ask before overwriting
    if existing_skills and not silent:
        from rich.console import Console
        con = Console()
        names = ", ".join(s.name for s in existing_skills)
        con.print(f"  [yellow]Skills already present:[/yellow] {names}")
        answer = input("  Overwrite with latest built-in versions? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            for skill_dir in existing_skills:
                dst = workspace_skills_dir / skill_dir.name
                shutil.rmtree(dst)
                shutil.copytree(skill_dir, dst)
                copied.append(skill_dir.name)
        else:
            con.print("  [dim]Skipped — existing skills unchanged.[/dim]")

    if copied and not silent:
        from rich.console import Console
        for name in copied:
            Console().print(f"  [dim]Synced skill {name} to workspace/skills/{name}[/dim]")

    return copied


def build_assistant_message(
    content: str | None,
    tool_calls: list[dict[str, Any]] | None = None,
    reasoning_content: str | None = None,
    thinking_blocks: list[dict] | None = None,
) -> dict[str, Any]:
    """Build a provider-safe assistant message with optional reasoning fields."""
    msg: dict[str, Any] = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    if reasoning_content is not None:
        msg["reasoning_content"] = reasoning_content
    if thinking_blocks:
        msg["thinking_blocks"] = thinking_blocks
    return msg


def estimate_prompt_tokens(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> int:
    """Estimate prompt tokens with tiktoken."""
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "")
            parts.append(role)
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        txt = part.get("text", "")
                        if txt:
                            parts.append(txt)
            if msg.get("name"):
                parts.append(msg["name"])
            if msg.get("tool_call_id"):
                parts.append(msg["tool_call_id"])
            if msg.get("tool_calls"):
                parts.append(json.dumps(msg["tool_calls"], ensure_ascii=False))
        if tools:
            parts.append(json.dumps(tools, ensure_ascii=False))
        base = len(enc.encode("\n".join(parts)))
        return base + max(0, len(messages)) * 4
    except Exception:
        return 0


def estimate_message_tokens(message: dict[str, Any]) -> int:
    """Estimate prompt tokens contributed by one persisted message."""
    content = message.get("content")
    parts: list[str] = []
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
                if text:
                    parts.append(text)
            else:
                parts.append(json.dumps(part, ensure_ascii=False))
    elif content is not None:
        parts.append(json.dumps(content, ensure_ascii=False))

    for key in ("name", "tool_call_id"):
        value = message.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
    if message.get("tool_calls"):
        parts.append(json.dumps(message["tool_calls"], ensure_ascii=False))

    payload = "\n".join(parts)
    if not payload:
        return 1
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return max(1, len(enc.encode(payload)))
    except Exception:
        return max(1, len(payload) // 4)


def estimate_prompt_tokens_chain(
    provider: Any,
    model: str | None,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> tuple[int, str]:
    """Estimate prompt tokens via provider counter first, then tiktoken fallback."""
    provider_counter = getattr(provider, "estimate_prompt_tokens", None)
    if callable(provider_counter):
        try:
            tokens, source = provider_counter(messages, tools, model)
            if isinstance(tokens, (int, float)) and tokens > 0:
                return int(tokens), str(source or "provider_counter")
        except Exception:
            pass

    estimated = estimate_prompt_tokens(messages, tools)
    if estimated > 0:
        return int(estimated), "tiktoken"
    return 0, "none"


def sync_skills(workspace: Path) -> list[str]:
    """Sync built-in skills to workspace/skills without asking for confirmation."""
    return _sync_builtin_skills_to_workspace(workspace, silent=True)


def sync_profiles(workspace: Path) -> list[str]:
    """Sync built-in profile templates to workspace/profiles on startup.

    - Creates profiles/ directory if missing.
    - Writes manifest.json with built-in entries; merges with existing
      user entries without overwriting them. Repairs corrupted manifests.
    - Copies each built-in profile's SOUL.md only if it doesn't already
      exist (user customizations are preserved).
    """
    import json as _json
    from importlib.resources import files as pkg_files

    try:
        tpl = pkg_files("shibaclaw") / "templates" / "profiles"
    except Exception:
        return []
    if not tpl.is_dir():
        return []

    added: list[str] = []
    profiles_dest = workspace / "profiles"
    profiles_dest.mkdir(parents=True, exist_ok=True)

    # ── Manifest: merge built-in entries ────────────────────────────
    manifest_src = tpl / "manifest.json"
    manifest_dest = profiles_dest / "manifest.json"
    if manifest_src.is_file():
        builtin_manifest = _json.loads(manifest_src.read_text(encoding="utf-8"))

        existing: dict = {}
        if manifest_dest.exists():
            try:
                raw = _json.loads(manifest_dest.read_text(encoding="utf-8"))
                existing = raw if isinstance(raw, dict) else {}
            except Exception:
                existing = {}

        # Ensure every built-in entry exists; update new fields on existing entries
        changed = False
        for pid, meta in builtin_manifest.items():
            if pid not in existing:
                existing[pid] = meta
                changed = True
            else:
                # Merge new fields from template without overwriting user edits
                for key, val in meta.items():
                    if key not in existing[pid]:
                        existing[pid][key] = val
                        changed = True

        if changed or not manifest_dest.exists():
            manifest_dest.write_text(
                _json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            added.append("profiles/manifest.json")

    # ── Profile SOUL.md files ───────────────────────────────────────
    for profile_dir in tpl.iterdir():
        if profile_dir.is_dir():
            soul_src = profile_dir / "SOUL.md"
            dest_dir = profiles_dest / profile_dir.name
            soul_dest = dest_dir / "SOUL.md"
            if soul_src.is_file() and not soul_dest.exists():
                dest_dir.mkdir(exist_ok=True)
                soul_dest.write_text(
                    soul_src.read_text(encoding="utf-8"), encoding="utf-8"
                )
                added.append(f"profiles/{profile_dir.name}/SOUL.md")

    return added


def sync_workspace_templates(workspace: Path, silent: bool = False) -> list[str]:
    """Sync bundled templates to workspace.

    New files are created automatically.  If template .md files already
    exist the user is asked whether to overwrite them (they may have been
    customised).  In *silent* mode existing files are never touched.
    """
    from importlib.resources import files as pkg_files
    try:
        tpl = pkg_files("shibaclaw") / "templates"
    except Exception:
        return []
    if not tpl.is_dir():
        return []

    added: list[str] = []

    # Collect templates split into new vs existing
    new_templates: list[tuple[Any, Path]] = []
    existing_templates: list[tuple[Any, Path]] = []

    for item in tpl.iterdir():
        if item.name.endswith(".md") and not item.name.startswith("."):
            dest = workspace / item.name
            (existing_templates if dest.exists() else new_templates).append((item, dest))

    mem_tpl = tpl / "memory" / "MEMORY.md"
    mem_dest = workspace / "memory" / "MEMORY.md"
    (existing_templates if mem_dest.exists() else new_templates).append((mem_tpl, mem_dest))

    hist_dest = workspace / "memory" / "HISTORY.md"
    if not hist_dest.exists():
        new_templates.append((None, hist_dest))

    def _write(src, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text(encoding="utf-8") if src else "", encoding="utf-8")
        added.append(str(dest.relative_to(workspace)))

    # New templates — create without asking
    for src, dest in new_templates:
        _write(src, dest)

    # Existing templates — ask before overwriting
    if existing_templates and not silent:
        from rich.console import Console
        con = Console()
        names = ", ".join(d.name for _, d in existing_templates)
        con.print(f"  [yellow]Templates already customised:[/yellow] {names}")
        answer = input("  Overwrite with defaults? [y/N] ").strip().lower()
        if answer in ("y", "yes"):
            for src, dest in existing_templates:
                _write(src, dest)
        else:
            con.print("  [dim]Skipped — your templates unchanged.[/dim]")

    (workspace / "skills").mkdir(exist_ok=True)

    # ── Sync built-in profiles ──────────────────────────────────────
    profiles_tpl = tpl / "profiles"
    if profiles_tpl.is_dir():
        profiles_dest = workspace / "profiles"
        profiles_dest.mkdir(exist_ok=True)

        # Copy manifest (merge built-in entries, don't overwrite user edits)
        manifest_src = profiles_tpl / "manifest.json"
        manifest_dest = profiles_dest / "manifest.json"
        if manifest_src.is_file():
            import json as _json
            builtin_manifest = _json.loads(manifest_src.read_text(encoding="utf-8"))
            if manifest_dest.exists():
                try:
                    raw = _json.loads(manifest_dest.read_text(encoding="utf-8"))
                    existing = raw if isinstance(raw, dict) else {}
                except Exception:
                    existing = {}
                for pid, meta in builtin_manifest.items():
                    if pid not in existing:
                        existing[pid] = meta
                    else:
                        for key, val in meta.items():
                            if key not in existing[pid]:
                                existing[pid][key] = val
                manifest_dest.write_text(
                    _json.dumps(existing, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                _write(manifest_src, manifest_dest)

        # Copy profile directories (only if they don't exist yet)
        for profile_dir in profiles_tpl.iterdir():
            if profile_dir.is_dir():
                dest_dir = profiles_dest / profile_dir.name
                soul_src = profile_dir / "SOUL.md"
                soul_dest = dest_dir / "SOUL.md"
                if soul_src.is_file() and not soul_dest.exists():
                    dest_dir.mkdir(exist_ok=True)
                    _write(soul_src, soul_dest)

    if added and not silent:
        from rich.console import Console
        for name in added:
            Console().print(f"  [dim]Created {name}[/dim]")
    return added
