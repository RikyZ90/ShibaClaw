"""Tests for shibaclaw.helpers.system — OS abstraction layer."""

from __future__ import annotations

import sys
from socket import AF_INET, SOCK_STREAM, socket
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# get_os_type
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "platform_system, expected",
    [
        ("Windows", "windows"),
        ("Linux", "linux"),
        ("Darwin", "darwin"),
        ("FreeBSD", "linux"),  # Unknown systems fall back to 'linux'
    ],
)
def test_get_os_type(platform_system: str, expected: str) -> None:
    from shibaclaw.helpers.system import get_os_type

    with mock.patch("platform.system", return_value=platform_system):
        assert get_os_type() == expected


# ---------------------------------------------------------------------------
# is_running_in_docker
# ---------------------------------------------------------------------------

def test_is_running_in_docker_via_dockerenv(tmp_path) -> None:
    from shibaclaw.helpers.system import is_running_in_docker

    dockerenv = tmp_path / ".dockerenv"
    dockerenv.touch()
    with mock.patch("os.path.exists", side_effect=lambda p: str(p) == "/.dockerenv" or p == str(dockerenv)):
        # Patch os.path.exists to return True for /.dockerenv
        with mock.patch("os.path.exists", return_value=True):
            assert is_running_in_docker() is True


def test_is_running_in_docker_via_env_var() -> None:
    from shibaclaw.helpers.system import is_running_in_docker

    with mock.patch("os.path.exists", return_value=False):
        with mock.patch.dict("os.environ", {"DOCKER_CONTAINER": "1"}, clear=False):
            assert is_running_in_docker() is True


def test_is_running_in_docker_false() -> None:
    from shibaclaw.helpers.system import is_running_in_docker

    with mock.patch("os.path.exists", return_value=False):
        with mock.patch.dict("os.environ", {}, clear=True):
            # No cgroup file on Windows, OSError is silently caught
            assert is_running_in_docker() is False


# ---------------------------------------------------------------------------
# is_running_in_pip_env
# ---------------------------------------------------------------------------

def test_is_running_in_pip_env_venv(monkeypatch) -> None:
    from shibaclaw.helpers import system

    monkeypatch.setattr(system.sys, "prefix", "/some/venv")
    monkeypatch.setattr(system.sys, "base_prefix", "/usr")
    # Ensure legacy attribute is absent
    if hasattr(system.sys, "real_prefix"):
        monkeypatch.delattr(system.sys, "real_prefix")

    from importlib import reload
    # Re-import to pick up monkeypatched values at call time (functions read sys at call time)
    assert system.is_running_in_pip_env() is True


def test_is_running_in_pip_env_no_venv(monkeypatch) -> None:
    from shibaclaw.helpers import system

    monkeypatch.setattr(system.sys, "prefix", "/usr")
    monkeypatch.setattr(system.sys, "base_prefix", "/usr")
    if hasattr(system.sys, "real_prefix"):
        monkeypatch.delattr(system.sys, "real_prefix")

    assert system.is_running_in_pip_env() is False


def test_is_running_in_pip_env_legacy_virtualenv(monkeypatch) -> None:
    from shibaclaw.helpers import system

    monkeypatch.setattr(system.sys, "prefix", "/usr")
    monkeypatch.setattr(system.sys, "base_prefix", "/usr")
    monkeypatch.setattr(system.sys, "real_prefix", "/real/base", raising=False)

    assert system.is_running_in_pip_env() is True


# ---------------------------------------------------------------------------
# TCP port helpers
# ---------------------------------------------------------------------------

def test_is_tcp_port_available_false_when_port_is_bound() -> None:
    from shibaclaw.helpers.system import is_tcp_port_available

    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bound_port = sock.getsockname()[1]
        assert is_tcp_port_available("127.0.0.1", bound_port) is False


def test_find_free_tcp_port_skips_excluded_port() -> None:
    from shibaclaw.helpers.system import find_free_tcp_port

    excluded = find_free_tcp_port("127.0.0.1")
    selected = find_free_tcp_port("127.0.0.1", exclude={excluded})
    assert selected != excluded


# ---------------------------------------------------------------------------
# execute_command
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_command_linux_echo() -> None:
    from shibaclaw.helpers.system import execute_command

    mock_proc = mock.AsyncMock()
    mock_proc.communicate = mock.AsyncMock(return_value=(b"hello\n", b""))
    mock_proc.returncode = 0

    with mock.patch("shibaclaw.helpers.system.get_os_type", return_value="linux"):
        with mock.patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            rc, stdout, stderr = await execute_command("echo hello")

    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "/bin/sh"
    assert "-c" in call_args
    assert rc == 0
    assert "hello" in stdout


@pytest.mark.asyncio
async def test_execute_command_windows_echo() -> None:
    from shibaclaw.helpers.system import execute_command

    # Only meaningful on actual Windows; on Linux we mock create_subprocess_exec
    mock_proc = mock.AsyncMock()
    mock_proc.communicate = mock.AsyncMock(return_value=(b"hello\r\n", b""))
    mock_proc.returncode = 0

    with mock.patch("shibaclaw.helpers.system.get_os_type", return_value="windows"):
        with mock.patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            rc, stdout, stderr = await execute_command("echo hello")

    mock_exec.assert_called_once()
    call_args = mock_exec.call_args[0]
    assert call_args[0] == "powershell.exe"
    assert "-Command" in call_args
    assert rc == 0
    assert "hello" in stdout


@pytest.mark.asyncio
async def test_execute_command_timeout() -> None:
    import asyncio
    from shibaclaw.helpers.system import execute_command

    async def _slow_communicate():
        await asyncio.sleep(999)
        return b"", b""

    mock_proc = mock.AsyncMock()
    mock_proc.communicate = _slow_communicate
    mock_proc.returncode = None
    mock_proc.kill = mock.MagicMock()
    mock_proc.wait = mock.AsyncMock()

    with mock.patch("shibaclaw.helpers.system.get_os_type", return_value="linux"):
        with mock.patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            rc, stdout, stderr = await execute_command("sleep 999", timeout=0.05)

    assert rc == -1
    assert "timed out" in stderr


# ---------------------------------------------------------------------------
# skills OS gating
# ---------------------------------------------------------------------------

def test_skills_os_gating_windows(tmp_path) -> None:
    """Skills with os=['windows'] must be available only on Windows."""
    from shibaclaw.agent.skills import SkillsLoader

    # Create a fake skill restricted to Windows
    skill_dir = tmp_path / "win-only"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        '---\nname: win-only\ndescription: Windows only\n'
        'metadata: {"shibaclaw":{"os":["windows"]}}\n---\n# Win only\n'
    )

    loader = SkillsLoader(workspace=tmp_path, builtin_skills_dir=tmp_path)

    with mock.patch("shibaclaw.agent.skills.platform.system", return_value="Windows"):
        available = {s["name"] for s in loader.list_skills(filter_unavailable=True)}
        assert "win-only" in available

    with mock.patch("shibaclaw.agent.skills.platform.system", return_value="Linux"):
        available = {s["name"] for s in loader.list_skills(filter_unavailable=True)}
        assert "win-only" not in available


def test_skills_os_gating_linux(tmp_path) -> None:
    """Skills with os=['darwin','linux'] must be excluded on Windows."""
    from shibaclaw.agent.skills import SkillsLoader

    skill_dir = tmp_path / "posix-only"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        '---\nname: posix-only\ndescription: POSIX only\n'
        'metadata: {"shibaclaw":{"os":["darwin","linux"]}}\n---\n# POSIX only\n'
    )

    loader = SkillsLoader(workspace=tmp_path, builtin_skills_dir=tmp_path)

    with mock.patch("shibaclaw.agent.skills.platform.system", return_value="Windows"):
        available = {s["name"] for s in loader.list_skills(filter_unavailable=True)}
        assert "posix-only" not in available

    with mock.patch("shibaclaw.agent.skills.platform.system", return_value="Linux"):
        available = {s["name"] for s in loader.list_skills(filter_unavailable=True)}
        assert "posix-only" in available
