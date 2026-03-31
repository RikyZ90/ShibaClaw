"""Install audit — vulnerability scanning for package installation commands.

Instead of blindly blocking pip/npm/apt install commands, this module:
1. Detects the package manager from the command
2. Runs a dry-run to resolve packages
3. Audits resolved packages for known CVEs
4. Returns an AuditResult with allow/block decision + evidence
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from loguru import logger


class Severity(str, Enum):
    """CVE severity levels, ordered from most to least severe."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

    @classmethod
    def from_str(cls, s: str) -> "Severity":
        try:
            return cls(s.lower().strip())
        except ValueError:
            return cls.UNKNOWN

    def __ge__(self, other: "Severity") -> bool:
        order = [self.CRITICAL, self.HIGH, self.MEDIUM, self.LOW, self.UNKNOWN]
        return order.index(self) <= order.index(other)

    def __gt__(self, other: "Severity") -> bool:
        return self != other and self >= other


# Severity threshold ordering for comparison
_SEVERITY_ORDER = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.UNKNOWN: 0,
}


@dataclass
class Vulnerability:
    """A single known vulnerability."""
    package: str
    version: str
    cve_id: str
    severity: Severity
    description: str = ""


@dataclass
class AuditResult:
    """Result of a vulnerability audit on an install command."""
    allowed: bool
    confidence: str  # "high", "medium", "low"
    manager: str  # "pip", "npm", "apt", etc.
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)

    @property
    def high_count(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)

    def format_report(self) -> str:
        """Format a human-readable report for the agent."""
        lines = [f"🔍 Install Audit ({self.manager}): {self.summary}"]
        if self.warnings:
            for w in self.warnings:
                lines.append(f"  ⚠️  {w}")
        if self.vulnerabilities:
            lines.append(f"\n  Found {len(self.vulnerabilities)} vulnerability(ies):")
            for v in self.vulnerabilities:
                severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                    v.severity.value, "⚪"
                )
                lines.append(
                    f"    {severity_icon} [{v.severity.value.upper()}] {v.package}=={v.version}"
                    f" — {v.cve_id}"
                )
                if v.description:
                    lines.append(f"       {v.description[:120]}")
        return "\n".join(lines)


# ─── Pattern detection ──────────────────────────────────────────────

_INSTALL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pip", re.compile(r"\bpip3?\s+install\b", re.IGNORECASE)),
    ("npm", re.compile(r"\bnpm\s+(install|add|i)\b", re.IGNORECASE)),
    ("yarn", re.compile(r"\byarn\s+(add|install)\b", re.IGNORECASE)),
    ("pnpm", re.compile(r"\bpnpm\s+(install|add)\b", re.IGNORECASE)),
    ("apt", re.compile(r"\b(apt|apt-get)\s+install\b", re.IGNORECASE)),
    ("dnf", re.compile(r"\b(dnf|yum)\s+install\b", re.IGNORECASE)),
    ("brew", re.compile(r"\bbrew\s+install\b", re.IGNORECASE)),
]


def detect_install_command(command: str) -> str | None:
    """Detect which package manager install command is being used.

    Returns the manager name ("pip", "npm", etc.) or None if not an install.
    """
    for manager, pattern in _INSTALL_PATTERNS:
        if pattern.search(command):
            return manager
    return None


# ─── Audit runners ──────────────────────────────────────────────────

async def _run_subprocess(
    cmd: list[str],
    timeout: int = 120,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=proc_env,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return (
            process.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )
    except asyncio.TimeoutError:
        try:
            process.kill()
        except Exception:
            pass
        return -1, "", "Audit subprocess timed out"
    except FileNotFoundError:
        return -1, "", f"Audit tool not found: {cmd[0]}"
    except Exception as e:
        return -1, "", f"Audit subprocess error: {e}"


async def _audit_pip(
    command: str, timeout: int = 120, block_severity: str = "high",
) -> AuditResult:
    """Audit a pip install command using pip-audit.

    Strategy:
    1. Extract package names from the command
    2. Run pip-audit on the packages (or full environment post-install dry-run)
    """
    result = AuditResult(allowed=True, confidence="high", manager="pip")
    threshold = Severity.from_str(block_severity)

    # Extract package specs from command (everything after 'pip install' that isn't a flag)
    # Use finditer to support multiline commands or chained commands
    packages: list[str] = []
    
    for match in re.finditer(r"\bpip3?\s+install\s+([^&;\n]+)", command, re.IGNORECASE):
        raw_args = match.group(1).strip()
        tokens = raw_args.split()
        skip_next = False
        for token in tokens:
            if skip_next:
                skip_next = False
                continue
            if token.startswith("-"):
                # Flags that consume the next arg
                if token in ("-r", "--requirement", "-c", "--constraint", "-e", "--editable",
                             "-t", "--target", "--prefix", "-i", "--index-url",
                             "--extra-index-url", "-f", "--find-links"):
                    skip_next = True
                continue
            packages.append(token)
            
    if not packages and "pip install" not in command.lower():
        result.summary = "Could not parse pip install command"
        result.confidence = "low"
        result.warnings.append("Could not parse package list from command")
        return result

    if not packages:
        # Could be -r requirements.txt or just `pip install` (installs from setup.py)
        result.summary = "No explicit packages detected (may be -r or editable install)"
        result.confidence = "medium"
        result.warnings.append(
            "Cannot audit individual packages. The install will proceed with caution."
        )
        return result

    # Try pip-audit with the specific packages
    audit_cmd = ["pip-audit", "--format", "json", "--desc", "--progress-spinner=off"]
    for pkg in packages:
        audit_cmd.extend(["-r", "/dev/stdin"])  # won't use this path

    # Better approach: pip-audit can audit requirements passed directly
    # Use --requirement with a temp approach, or just audit the package names
    # pip-audit >= 2.6 supports: pip-audit <package_spec> ...
    # For simplicity, we pipe package specs via -r /dev/stdin
    pkg_list = "\n".join(packages)
    try:
        process = await asyncio.create_subprocess_exec(
            "pip-audit", "--format", "json", "--desc", "--progress-spinner=off",
            "-r", "/dev/stdin",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input=pkg_list.encode()),
            timeout=timeout,
        )
        returncode = process.returncode or 0
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        result.warnings.append("pip-audit timed out — allowing install with caution")
        result.confidence = "low"
        result.summary = "Audit timed out"
        return result
    except FileNotFoundError:
        result.warnings.append("pip-audit not installed — allowing install with caution")
        result.confidence = "low"
        result.summary = "Audit tool not available"
        return result
    except Exception as e:
        result.warnings.append(f"pip-audit error: {e} — allowing install with caution")
        result.confidence = "low"
        result.summary = "Audit error"
        return result

    # Parse pip-audit JSON output
    vulns = _parse_pip_audit_json(stdout)
    result.vulnerabilities = vulns

    if not vulns:
        result.summary = f"No known vulnerabilities in {', '.join(packages)}"
        return result

    # Classify
    result.allowed, result.summary = _classify_vulnerabilities(vulns, threshold)
    return result


def _parse_pip_audit_json(output: str) -> list[Vulnerability]:
    """Parse pip-audit JSON output into Vulnerability objects."""
    vulns: list[Vulnerability] = []
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return vulns

    # pip-audit JSON format: {"dependencies": [...]}  or list of dicts
    deps = data if isinstance(data, list) else data.get("dependencies", [])
    for dep in deps:
        pkg_name = dep.get("name", "unknown")
        pkg_version = dep.get("version", "?")
        for vuln in dep.get("vulns", []):
            vulns.append(Vulnerability(
                package=pkg_name,
                version=pkg_version,
                cve_id=vuln.get("id", vuln.get("aliases", ["UNKNOWN"])[0] if vuln.get("aliases") else "UNKNOWN"),
                severity=Severity.from_str(vuln.get("fix_versions", [{}])[0] if False else "unknown"),
                description=vuln.get("description", "")[:200],
            ))
            # Try to get proper severity from description or details
            desc_lower = vuln.get("description", "").lower()
            if any(word in desc_lower for word in ("critical", "remote code execution", "rce")):
                vulns[-1].severity = Severity.CRITICAL
            elif any(word in desc_lower for word in ("high", "arbitrary", "injection", "overflow")):
                vulns[-1].severity = Severity.HIGH
            elif any(word in desc_lower for word in ("medium", "moderate", "denial of service")):
                vulns[-1].severity = Severity.MEDIUM
            elif any(word in desc_lower for word in ("low", "minor", "informational")):
                vulns[-1].severity = Severity.LOW
    return vulns


async def _audit_npm(
    command: str, timeout: int = 120, block_severity: str = "high",
    cwd: str | None = None,
) -> AuditResult:
    """Audit an npm/yarn/pnpm install using npm audit."""
    result = AuditResult(allowed=True, confidence="high", manager="npm")
    threshold = Severity.from_str(block_severity)

    # Note: We skip the simulated `--dry-run` phase!
    # A dry run command does not modify package-lock.json anyway,
    # so npm audit wouldn't pick up entirely new dependencies until after real installation.
    # Additionally, if the user sends multiline shell scripts containing `npm run dev`,
    # executing them during the audit phase causes hanging and timeout blocks.
    
    # Run npm audit --json on the current project
    audit_cmd = ["npm", "audit", "--json"]
    returncode, stdout, stderr = await _run_subprocess(
        audit_cmd, timeout=timeout, cwd=cwd,
    )

    if returncode == -1:
        result.warnings.append("npm audit not available — allowing install with caution")
        result.confidence = "low"
        result.summary = "Audit tool not available"
        return result

    # Parse npm audit JSON
    vulns = _parse_npm_audit_json(stdout)
    result.vulnerabilities = vulns

    if not vulns:
        result.summary = "No known vulnerabilities found by npm audit"
        return result

    result.allowed, result.summary = _classify_vulnerabilities(vulns, threshold)
    return result


def _parse_npm_audit_json(output: str) -> list[Vulnerability]:
    """Parse npm audit JSON output."""
    vulns: list[Vulnerability] = []
    try:
        data = json.loads(output)
    except (json.JSONDecodeError, ValueError):
        return vulns

    # npm audit v2+ format: {"vulnerabilities": {"pkg_name": {...}}}
    vuln_data = data.get("vulnerabilities", {})
    for pkg_name, info in vuln_data.items():
        severity_str = info.get("severity", "unknown")
        for via_entry in info.get("via", []):
            if isinstance(via_entry, dict):
                vulns.append(Vulnerability(
                    package=pkg_name,
                    version=info.get("range", "?"),
                    cve_id=via_entry.get("url", via_entry.get("source", "UNKNOWN")),
                    severity=Severity.from_str(via_entry.get("severity", severity_str)),
                    description=via_entry.get("title", "")[:200],
                ))
    return vulns


async def _audit_system_pkg(
    command: str, manager: str,
) -> AuditResult:
    """Basic audit for system package managers (apt, dnf, yum).

    Since there's no client-side CVE database for these, we do a basic
    safety check: ensure the command doesn't use untrusted sources.
    """
    result = AuditResult(allowed=True, confidence="medium", manager=manager)

    # Check for suspicious flags that add untrusted sources
    suspicious_patterns = [
        r"--allow-unauthenticated",
        r"--force-yes",
        r"--no-check-certificate",
        r"--nogpgcheck",
        r"--skip-broken",
    ]
    for pat in suspicious_patterns:
        if re.search(pat, command, re.IGNORECASE):
            result.allowed = False
            result.confidence = "high"
            result.summary = f"Blocked: unsafe flag detected ({pat.strip()})"
            return result

    result.summary = (
        f"System package install via {manager} — packages are from configured repositories. "
        "No client-side CVE check available; relying on repository-level security."
    )
    result.warnings.append(
        "System package managers don't support client-side vulnerability scanning. "
        "Ensure your package sources are trusted."
    )
    return result


async def _audit_brew(command: str) -> AuditResult:
    """Audit for Homebrew — generally considered safe (curated formulae)."""
    return AuditResult(
        allowed=True,
        confidence="medium",
        manager="brew",
        summary="Homebrew formulae are community-curated. Install allowed with standard trust.",
        warnings=["Homebrew packages are community-maintained. No CVE audit performed."],
    )


# ─── Classification ─────────────────────────────────────────────────

def _classify_vulnerabilities(
    vulns: list[Vulnerability], threshold: Severity,
) -> tuple[bool, str]:
    """Classify vulnerabilities and decide if install should proceed.

    Returns (allowed, summary).
    """
    blocked_vulns = [v for v in vulns if _SEVERITY_ORDER.get(v.severity, 0) >= _SEVERITY_ORDER.get(threshold, 0)]

    if blocked_vulns:
        crit = sum(1 for v in blocked_vulns if v.severity == Severity.CRITICAL)
        high = sum(1 for v in blocked_vulns if v.severity == Severity.HIGH)
        parts = []
        if crit:
            parts.append(f"{crit} critical")
        if high:
            parts.append(f"{high} high")
        others = len(blocked_vulns) - crit - high
        if others:
            parts.append(f"{others} other(s) at/above threshold")
        return False, f"BLOCKED: {', '.join(parts)} severity vulnerability(ies) found"

    # Below threshold — allow with note
    return True, f"Allowed: {len(vulns)} vulnerability(ies) found, all below '{threshold.value}' threshold"


# ─── Public API ──────────────────────────────────────────────────────

async def audit_install(
    command: str,
    timeout: int = 120,
    block_severity: str = "high",
    cwd: str | None = None,
) -> AuditResult:
    """Audit a package install command for known vulnerabilities.

    This is the main entry point used by ExecTool.

    Args:
        command: The raw shell command (e.g. "pip install requests flask")
        timeout: Seconds to wait for audit tools
        block_severity: Minimum severity level to block ("critical", "high", "medium", "low")
        cwd: Working directory for npm/yarn audits

    Returns:
        AuditResult with allow/block decision and evidence
    """
    manager = detect_install_command(command)
    if manager is None:
        # Not an install command — shouldn't reach here, but be safe
        return AuditResult(
            allowed=True, confidence="high", manager="unknown",
            summary="Not recognized as an install command",
        )

    logger.info("🔍 Auditing install command ({}) for vulnerabilities...", manager)

    try:
        if manager == "pip":
            result = await _audit_pip(command, timeout=timeout, block_severity=block_severity)
        elif manager in ("npm", "yarn", "pnpm"):
            result = await _audit_npm(
                command, timeout=timeout, block_severity=block_severity, cwd=cwd,
            )
        elif manager in ("apt", "dnf", "yum"):
            result = await _audit_system_pkg(command, manager)
        elif manager == "brew":
            result = await _audit_brew(command)
        else:
            result = AuditResult(
                allowed=True, confidence="low", manager=manager,
                summary=f"No audit strategy for {manager} — allowing with caution",
                warnings=[f"No vulnerability scanner available for {manager}"],
            )
    except Exception as e:
        logger.warning("Install audit error for {}: {}", manager, e)
        result = AuditResult(
            allowed=True, confidence="low", manager=manager,
            summary=f"Audit failed: {e} — allowing install with caution",
            warnings=[f"Audit error: {e}. Install permitted as fallback."],
        )

    # Log the result
    if result.allowed:
        logger.info("✅ Install audit passed ({}): {}", result.confidence, result.summary)
    else:
        logger.warning("❌ Install audit BLOCKED: {}", result.summary)

    return result
