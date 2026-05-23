"""Network security utilities — SSRF protection and internal URL detection."""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Sequence
from urllib.parse import urlparse

_BLOCKED_NETWORKS: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # unique local
    ipaddress.ip_network("fe80::/10"),  # link-local v6
]

_URL_RE = re.compile(r"https?://[^\s\"'`;|<>]+", re.IGNORECASE)


def _is_private(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _resolve_all_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Resolve *hostname* and return all IP addresses."""
    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for info in infos:
        try:
            addrs.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    return addrs


def _check_ips(
    hostname: str,
    addrs: list[ipaddress.IPv4Address | ipaddress.IPv6Address],
) -> tuple[bool, str]:
    """Return (ok, error) – False if any address is private/internal."""
    for addr in addrs:
        if _is_private(addr):
            return False, f"Blocked: {hostname} resolves to private/internal address {addr}"
    return True, ""


def validate_url_target(url: str) -> tuple[bool, str]:
    """Validate a URL is safe to fetch: scheme, hostname, and resolved IPs.

    Returns (ok, error_message).  When ok is True, error_message is empty.
    """
    try:
        p = urlparse(url)
    except Exception as e:
        return False, str(e)

    if p.scheme not in ("http", "https"):
        return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
    if not p.netloc:
        return False, "Missing domain"

    hostname = p.hostname
    if not hostname:
        return False, "Missing hostname"

    addrs = _resolve_all_ips(hostname)
    if not addrs:
        return False, f"Cannot resolve hostname: {hostname}"

    return _check_ips(hostname, addrs)


def resolve_and_pin(url: str) -> tuple[bool, str, list[str]]:
    """Resolve *url*, validate all IPs, and return the pinned addresses.

    This is the DNS-rebinding-safe entry point.  Callers should connect
    **only** to the returned IP addresses so a second DNS lookup (which
    might return a different, internal IP) is never performed.

    Returns ``(ok, error, pinned_ips)``.
    ``pinned_ips`` are string representations of the resolved addresses.
    """
    try:
        p = urlparse(url)
    except Exception as e:
        return False, str(e), []

    if p.scheme not in ("http", "https"):
        return False, f"Only http/https allowed, got '{p.scheme or 'none'}'", []
    if not p.netloc:
        return False, "Missing domain", []

    hostname = p.hostname
    if not hostname:
        return False, "Missing hostname", []

    addrs = _resolve_all_ips(hostname)
    if not addrs:
        return False, f"Cannot resolve hostname: {hostname}", []

    ok, err = _check_ips(hostname, addrs)
    if not ok:
        return False, err, []

    return True, "", [str(a) for a in addrs]


def validate_resolved_url(url: str) -> tuple[bool, str]:
    """Validate an already-fetched URL (e.g. after redirect).

    Re-resolves the hostname and checks all resulting IPs.
    """
    try:
        p = urlparse(url)
    except Exception:
        return True, ""

    hostname = p.hostname
    if not hostname:
        return True, ""

    # If hostname is already an IP literal, check it directly.
    try:
        addr = ipaddress.ip_address(hostname)
        if _is_private(addr):
            return False, f"Redirect target is a private address: {addr}"
        return True, ""
    except ValueError:
        pass

    addrs = _resolve_all_ips(hostname)
    if not addrs:
        return True, ""
    return _check_ips(hostname, addrs)


def contains_internal_url(command: str) -> bool:
    """Return True if the command string contains a URL targeting an internal/private address."""
    for m in _URL_RE.finditer(command):
        url = m.group(0)
        ok, _ = validate_url_target(url)
        if not ok:
            return True
    return False
