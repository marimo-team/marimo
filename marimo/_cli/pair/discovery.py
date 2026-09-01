# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from pathlib import Path

PlatformName = Literal["posix", "windows", "wsl"]
Origin = Literal["local", "windows-host", "direct"]


class ProcessState(Enum):
    RUNNING = "running"
    NOT_RUNNING = "not_running"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RegistryLocation:
    path: Path
    origin: Origin


@dataclass(frozen=True)
class PairServer:
    server_id: str
    origin: Origin
    url: str | None
    started_at: str
    version: str


@dataclass(frozen=True)
class DiscoveryResult:
    servers: tuple[PairServer, ...]
    warnings: tuple[str, ...]


class DiscoveryEnvironment(Protocol):
    platform: PlatformName

    def registry_locations(self) -> tuple[RegistryLocation, ...]: ...

    def process_state(self, pid: int, origin: Origin) -> ProcessState: ...

    def gateway(self) -> str | None: ...

    def answers_marimo(self, url: str) -> bool: ...


@dataclass(frozen=True)
class _RegistryRecord:
    server_id: str
    pid: int
    host: str
    port: int
    base_url: str
    started_at: str
    version: str


_WINDOWS_LOOPBACK_HOSTS = frozenset(
    ("", "0.0.0.0", "::", "127.0.0.1", "localhost", "::1")
)
_PRIVATE_IPV4_NETWORKS = (
    IPv4Network("10.0.0.0/8"),
    IPv4Network("127.0.0.0/8"),
    IPv4Network("169.254.0.0/16"),
    IPv4Network("172.16.0.0/12"),
    IPv4Network("192.168.0.0/16"),
)


def _is_private_ipv4(host: str) -> bool:
    try:
        address = IPv4Address(host)
    except ValueError:
        return False
    return any(address in network for network in _PRIVATE_IPV4_NETWORKS)


def _candidate_hosts(
    *,
    host: str,
    port: int,
    origin: Origin,
    gateway: str | None,
    live_local_ports: set[int],
) -> tuple[str, ...]:
    if origin == "local":
        if host in ("", "0.0.0.0"):
            return ("127.0.0.1",)
        if host == "::":
            return ("::1",)
        return (host,)

    candidates: list[str] = []
    if host not in _WINDOWS_LOOPBACK_HOSTS:
        candidates.append(host)
    if gateway is not None and _is_private_ipv4(gateway):
        candidates.append(gateway)
    if host in _WINDOWS_LOOPBACK_HOSTS and port not in live_local_ports:
        candidates.append("127.0.0.1")
    return tuple(candidates)


def _read_registry_record(path: Path) -> _RegistryRecord | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None

    string_fields = (
        "server_id",
        "host",
        "base_url",
        "started_at",
        "version",
    )
    if any(not isinstance(data.get(field), str) for field in string_fields):
        return None
    if type(data.get("pid")) is not int or type(data.get("port")) is not int:
        return None
    return _RegistryRecord(
        server_id=data["server_id"],
        pid=data["pid"],
        host=data["host"],
        port=data["port"],
        base_url=data["base_url"],
        started_at=data["started_at"],
        version=data["version"],
    )


def _resolve_url(
    record: _RegistryRecord,
    *,
    origin: Origin,
    environment: DiscoveryEnvironment,
    live_local_ports: set[int],
) -> str | None:
    gateway = environment.gateway() if origin == "windows-host" else None
    for host in _candidate_hosts(
        host=record.host,
        port=record.port,
        origin=origin,
        gateway=gateway,
        live_local_ports=live_local_ports,
    ):
        connect_host = f"[{host}]" if ":" in host else host
        url = f"http://{connect_host}:{record.port}{record.base_url}"
        if environment.answers_marimo(url):
            return url
    return None


def discover_servers(
    environment: DiscoveryEnvironment | None = None,
) -> DiscoveryResult:
    if environment is None:
        raise NotImplementedError

    locations = sorted(
        enumerate(environment.registry_locations()),
        key=lambda item: (item[1].origin != "local", item[0]),
    )
    servers: list[PairServer] = []
    live_local_ports: set[int] = set()
    for _, location in locations:
        if not location.path.is_dir():
            continue
        for path in sorted(location.path.glob("*.json")):
            record = _read_registry_record(path)
            if record is None:
                continue
            state = environment.process_state(record.pid, location.origin)
            url = _resolve_url(
                record,
                origin=location.origin,
                environment=environment,
                live_local_ports=live_local_ports,
            )
            if state is not ProcessState.RUNNING and url is None:
                continue
            servers.append(
                PairServer(
                    server_id=record.server_id,
                    origin=location.origin,
                    url=url,
                    started_at=record.started_at,
                    version=record.version,
                )
            )
            if location.origin == "local":
                live_local_ports.add(record.port)
    return DiscoveryResult(servers=tuple(servers), warnings=())
