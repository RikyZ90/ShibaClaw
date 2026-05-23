"""OS abstraction layer for ShibaClaw.

Provides utilities for OS detection and cross-platform command execution,
so the rest of the codebase avoids direct platform checks scattered around.
"""

from __future__ import annotations

import asyncio
import os
import platform
import socket
import sys
from typing import Literal

OsType = Literal["windows", "linux", "darwin"]
InstallMethod = Literal["source", "pip", "docker", "exe"]


def get_os_type() -> OsType:
    """Return the current OS type: 'windows', 'linux', or 'darwin'."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    if system == "darwin":
        return "darwin"
    return "linux"


def is_running_in_docker() -> bool:
    """Return True if the process is running inside a Docker container.

    Checks for the presence of ``/.dockerenv`` (Linux containers) and the
    ``DOCKER_CONTAINER`` or ``container`` environment variables as fallbacks.
    """
    if os.path.exists("/.dockerenv"):
        return True
    if os.environ.get("DOCKER_CONTAINER", "").lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("container", ""):
        return True
    # Heuristic: cgroup v1 tasks file contains 'docker'
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except OSError:
        pass
    return False


def is_running_in_pip_env() -> bool:
    """Return True if the process is running inside a virtual environment.

    Compares ``sys.prefix`` against ``sys.base_prefix``; they differ whenever
    a venv / virtualenv is active. Also handles the legacy ``sys.real_prefix``
    attribute set by older virtualenv versions.
    """
    if hasattr(sys, "real_prefix"):
        return True
    return sys.prefix != sys.base_prefix


def is_running_as_exe() -> bool:
    """Return True when running inside a PyInstaller frozen bundle.

    PyInstaller sets ``sys.frozen = True`` and adds the ``sys._MEIPASS``
    attribute pointing to the temporary extraction directory.
    """
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_installation_method() -> InstallMethod:
    """Detect how ShibaClaw was installed / launched.

    Returns one of:

    * ``'exe'``    — frozen PyInstaller bundle (``sys.frozen``)
    * ``'docker'`` — running inside a Docker container
    * ``'pip'``    — running inside a virtual environment (pip / uv / pipx)
    * ``'source'`` — direct source checkout without a venv
    """
    if is_running_as_exe():
        return "exe"
    if is_running_in_docker():
        return "docker"
    if is_running_in_pip_env():
        return "pip"
    return "source"


def is_tcp_port_available(host: str, port: int) -> bool:
    """Return True when *host:port* can be bound by the current process."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
        return True
    except OSError:
        return False


def find_free_tcp_port(host: str = "127.0.0.1", *, exclude: set[int] | None = None) -> int:
    """Return a free TCP port bound on *host*, skipping any in *exclude*."""
    blocked = exclude or set()
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            port = sock.getsockname()[1]
        if port not in blocked:
            return port


async def execute_command(
    cmd: str,
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 60.0,
) -> tuple[int, str, str]:
    """Execute *cmd* using the appropriate shell for the current OS.

    On Windows the command is run via ``powershell.exe -Command``; on POSIX
    systems it is passed to ``/bin/sh -c``.

    Returns a ``(returncode, stdout, stderr)`` tuple.  On timeout the process
    is killed and ``returncode`` is set to -1.
    """
    os_type = get_os_type()

    import subprocess

    if os_type == "windows":
        # Use powershell.exe so callers get PowerShell semantics
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NonInteractive",
            "-NoProfile",
            "-Command",
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    else:
        process = await asyncio.create_subprocess_exec(
            "/bin/sh",
            "-c",
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        return -1, "", f"Command timed out after {timeout:.0f}s"

    returncode = process.returncode if process.returncode is not None else -1
    return returncode, stdout_bytes.decode("utf-8", errors="replace"), stderr_bytes.decode("utf-8", errors="replace")
