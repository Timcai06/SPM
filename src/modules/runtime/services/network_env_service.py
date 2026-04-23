from __future__ import annotations

import os
import subprocess
from contextlib import contextmanager
from typing import Iterator


PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)

SYSTEM_PROXY_FLAG_KEYS = (
    "HTTPEnable",
    "HTTPSEnable",
    "SOCKSEnable",
    "ProxyAutoConfigEnable",
    "ProxyAutoDiscoveryEnable",
)
TUNNEL_INTERFACE_PREFIXES = ("utun", "tun", "tap", "ppp", "ipsec")


@contextmanager
def without_process_proxies() -> Iterator[None]:
    """Temporarily clear common proxy environment variables for this process only."""

    original_values = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
    try:
        for key in PROXY_ENV_KEYS:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in original_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _read_scutil_proxy_flags() -> dict[str, str]:
    result = subprocess.run(
        ["scutil", "--proxy"],
        capture_output=True,
        text=True,
        check=True,
    )
    flags: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if " : " not in line:
            continue
        key, value = [part.strip() for part in line.split(" : ", 1)]
        flags[key] = value
    return flags


def _default_route_interface() -> str:
    result = subprocess.run(
        ["route", "-n", "get", "default"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        if line.strip().startswith("interface:"):
            return line.split(":", 1)[1].strip()
    return ""


def ensure_direct_network_or_die() -> None:
    proxy_flags = _read_scutil_proxy_flags()
    active_flags = [key for key in SYSTEM_PROXY_FLAG_KEYS if proxy_flags.get(key, "0") not in {"0", ""}]
    if active_flags:
        joined = ", ".join(active_flags)
        raise SystemExit(
            f"Collector direct-network preflight failed: macOS proxy settings are active ({joined}). "
            "Disable system/PAC/SOCKS proxies before running collection."
        )

    interface = _default_route_interface()
    if interface and interface.startswith(TUNNEL_INTERFACE_PREFIXES):
        raise SystemExit(
            f"Collector direct-network preflight failed: default route is using tunnel interface {interface}. "
            "Disable VPN/TUN/global proxy before running collection."
        )


@contextmanager
def direct_network_only() -> Iterator[None]:
    with without_process_proxies():
        ensure_direct_network_or_die()
        yield
