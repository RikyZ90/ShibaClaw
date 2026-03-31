"""Shell execution tool."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from loguru import logger

from shibaclaw.agent.tools.base import Tool
from shibaclaw.security.install_audit import AuditResult, audit_install, detect_install_command


class ExecTool(Tool):
    """Tool to execute shell commands."""

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        path_append: str = "",
        install_audit: bool = True,
        install_audit_timeout: int = 120,
        install_audit_block_severity: str = "high",
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.install_audit = install_audit
        self.install_audit_timeout = install_audit_timeout
        self.install_audit_block_severity = install_audit_block_severity
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",              # del /f, del /q
            r"\brmdir\s+/s\b",               # rmdir /s
            r"(?:^|[;&|]\s*)format\b",       # format (as standalone command only)
            r"\b(mkfs|diskpart)\b",          # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
            r"\b(eval|alias|export|source)\b", # environment/execution manipulation
            r"\bsudo\s+",                    # privilege escalation
            r"\b(nc|netcat|ncat)\b",         # networking/shells
            r"\b(bash|sh|zsh|dash)\s+-i\b",  # interactive shells
            r"\$\([^)]*\)",                                          # command substitution $()
            r"`[^`]*`",                                              # backtick execution
            r"\|\s*(sh|bash|zsh|dash|fish)\b",                      # pipe to shell
            r"\b(apt|apt-get|yum|dnf|brew)\s+(remove|purge)\b",      # system pkg removal (destructive)
            r"\bpip3?\s+(uninstall)\b",                              # pip uninstall (destructive)
            r"\b(npm|yarn|pnpm)\s+(remove|uninstall)\b",             # JS pkg removal (destructive)
            r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh|dash)\b",          # curl/wget pipe to shell
            r"<\([^)]*\)",                                           # bash process substitution <()
        ]
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self.path_append = path_append

    @property
    def name(self) -> str:
        return "exec"

    _MAX_TIMEOUT = 600
    _MAX_OUTPUT = 10_000

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command",
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        "Timeout in seconds. Increase for long-running commands "
                        "like compilation or installation (default 60, max 600)."
                    ),
                    "minimum": 1,
                    "maximum": 600,
                },
            },
            "required": ["command"],
        }

    # Extra deny patterns applied when restrict_to_workspace is True
    # (Interpreter blocks removed: agent should be able to run code it writes within the workspace)

    async def execute(
        self, command: str, working_dir: str | None = None,
        timeout: int | None = None, **kwargs: Any,
    ) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        # ── Smart Install Guard: audit before executing ──
        if self.install_audit:
            audit_result = await self._audit_install_command(command, cwd)
            if audit_result is not None and not audit_result.allowed:
                report = audit_result.format_report()
                return f"Error: Install blocked by vulnerability audit\n\n{report}"

        effective_timeout = min(timeout or self.timeout, self._MAX_TIMEOUT)

        env = os.environ.copy()
        if self.path_append:
            env["PATH"] = env.get("PATH", "") + os.pathsep + self.path_append

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=effective_timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                return f"Error: Command timed out after {effective_timeout} seconds"

            output_parts = []

            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))

            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")

            output_parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"

            # Head + tail truncation to preserve both start and end of output
            max_len = self._MAX_OUTPUT
            if len(result) > max_len:
                half = max_len // 2
                result = (
                    result[:half]
                    + f"\n\n... ({len(result) - max_len:,} chars truncated) ...\n\n"
                    + result[-half:]
                )

            # Append audit warnings to output if any
            if self.install_audit and hasattr(self, '_last_audit_result'):
                audit_res: AuditResult | None = self._last_audit_result
                self._last_audit_result = None
                if audit_res and audit_res.warnings:
                    warnings_text = "\n".join(f"⚠️  {w}" for w in audit_res.warnings)
                    result = f"{result}\n\n🔍 Install Audit Warnings:\n{warnings_text}"

            return result

        except Exception as e:
            return f"Error executing command: {str(e)}"

    async def _audit_install_command(
        self, command: str, cwd: str,
    ) -> AuditResult | None:
        """Check if command is an install and audit it. Returns None if not an install."""
        normalized = self._normalize_command(command)
        manager = detect_install_command(normalized)
        if manager is None:
            return None

        logger.info("🔍 Detected {} install command — running vulnerability audit", manager)
        result = await audit_install(
            command,
            timeout=self.install_audit_timeout,
            block_severity=self.install_audit_block_severity,
            cwd=cwd,
        )
        # Stash for appending warnings to output after execution
        self._last_audit_result = result
        return result

    @staticmethod
    def _normalize_command(cmd: str) -> str:
        """Normalize common encoding tricks before safety checks.

        Handles hex escapes (\\x41), unicode escapes (\\u0041),
        and dollar-single-quote ($'\\x41') that bypass naive regex blocklists.
        """
        import codecs
        result = cmd
        # Decode Python-style hex/unicode escapes: \x41 → A, \u0041 → A
        try:
            result = codecs.decode(result, "unicode_escape")
        except Exception:
            pass  # leave as-is if decode fails (e.g. invalid sequences)
        # Collapse excessive whitespace (tab, multiple spaces → single space)
        result = re.sub(r"\s+", " ", result)
        return result

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        # Normalize encoding tricks before checking
        normalized = self._normalize_command(cmd)
        lower = normalized.lower()

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        if self.allow_patterns:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

        from shibaclaw.security.network import contains_internal_url
        if contains_internal_url(cmd):
            return "Error: Command blocked by safety guard (internal/private URL detected)"

        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            # (Note: Interpreter execution is allowed within workspace limits)

            # Block output redirects to absolute paths outside workspace
            redirect_targets = re.findall(r">{1,2}\s*([^\s|&;]+)", normalized)
            cwd_path = Path(cwd).resolve()
            for target in redirect_targets:
                try:
                    t = Path(target).expanduser().resolve()
                    if t.is_absolute() and cwd_path not in t.parents and t != cwd_path:
                        return "Error: Command blocked by safety guard (redirect outside working dir)"
                except Exception:
                    continue

            for raw in self._extract_absolute_paths(cmd):
                try:
                    expanded = os.path.expandvars(raw.strip())
                    p = Path(expanded).expanduser().resolve()
                except Exception:
                    continue
                if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                    return "Error: Command blocked by safety guard (path outside working dir)"

        return None

    @staticmethod
    def _extract_absolute_paths(command: str) -> list[str]:
        win_paths = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)   # Windows: C:\...
        posix_paths = re.findall(r"(?:^|[\s|>'\"])(/[^\s\"'>;|<]+)", command) # POSIX: /absolute only
        home_paths = re.findall(r"(?:^|[\s|>'\"])(~[^\s\"'>;|<]*)", command) # POSIX/Windows home shortcut: ~
        return win_paths + posix_paths + home_paths
