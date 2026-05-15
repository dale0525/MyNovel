from __future__ import annotations

import socket
from ipaddress import ip_address
from urllib.parse import urlparse

from mynovel.update import UpdateManifest, fetch_update_manifest


_TRUSTED_UPDATE_HOSTS = frozenset(
    {
        "github.com",
        "github-releases.githubusercontent.com",
        "objects.githubusercontent.com",
        "raw.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
)


def fetch_safe_update_manifest(manifest_url: str) -> UpdateManifest:
    ensure_safe_update_url(manifest_url, "update manifest URL")
    manifest = fetch_update_manifest(manifest_url)
    ensure_safe_update_url(manifest.url, "update artifact URL")
    return manifest


def ensure_safe_update_url(raw_url: str, label: str) -> None:
    parsed = urlparse(raw_url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError(f"{label} must be an https URL.")
    host = parsed.hostname.strip().lower().rstrip(".")
    allowed_hosts = {allowed.strip().lower().rstrip(".") for allowed in _allowed_update_hosts()}
    if host not in allowed_hosts:
        raise ValueError(f"{label} host is not an allowed update host.")
    try:
        addresses = _resolve_update_host_addresses(host)
    except OSError as error:
        raise ValueError(f"{label} host could not be resolved.") from error
    if not addresses:
        raise ValueError(f"{label} host could not be resolved.")
    for raw_address in addresses:
        _ensure_global_update_address(raw_address, label)


def _allowed_update_hosts() -> frozenset[str]:
    return _TRUSTED_UPDATE_HOSTS


def _resolve_update_host_addresses(host: str) -> list[str]:
    addresses: list[str] = []
    seen: set[str] = set()
    for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM):
        raw_address = str(info[4][0]).split("%", maxsplit=1)[0]
        if raw_address in seen:
            continue
        seen.add(raw_address)
        addresses.append(raw_address)
    return addresses


def _ensure_global_update_address(raw_address: str, label: str) -> None:
    try:
        address = ip_address(raw_address)
    except ValueError:
        raise ValueError(f"{label} resolved to an invalid IP address.")
    if not address.is_global:
        raise ValueError(f"{label} cannot target private or local network addresses.")
