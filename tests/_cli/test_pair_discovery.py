# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, dataclass, field
from typing import TYPE_CHECKING

import pytest

from marimo._cli.pair.discovery import (
    DiscoveryResult,
    Origin,
    PairServer,
    PlatformName,
    ProcessState,
    RegistryLocation,
    _candidate_hosts,
    discover_servers,
)

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class FakeDiscoveryEnvironment:
    platform: PlatformName = "posix"
    locations: tuple[RegistryLocation, ...] = ()
    states: dict[tuple[int, Origin], ProcessState] = field(
        default_factory=dict
    )
    reachable_urls: set[str] = field(default_factory=set)
    gateway_address: str | None = None

    def registry_locations(self) -> tuple[RegistryLocation, ...]:
        return self.locations

    def process_state(self, pid: int, origin: Origin) -> ProcessState:
        return self.states.get((pid, origin), ProcessState.UNKNOWN)

    def gateway(self) -> str | None:
        return self.gateway_address

    def answers_marimo(self, url: str) -> bool:
        return url in self.reachable_urls


def _write_registry(path: Path, **overrides: object) -> None:
    record = {
        "server_id": "127.0.0.1:2718",
        "pid": 4242,
        "host": "127.0.0.1",
        "port": 2718,
        "base_url": "",
        "started_at": "2026-08-31T00:00:00+00:00",
        "version": "0.24.0",
        **overrides,
    }
    path.write_text(json.dumps(record))


def test_discovery_models_are_immutable(tmp_path: Path) -> None:
    location = RegistryLocation(path=tmp_path, origin="local")
    server = PairServer(
        server_id="127.0.0.1:2718",
        origin="local",
        url="http://127.0.0.1:2718",
        started_at="2026-08-31T00:00:00+00:00",
        version="0.24.0",
    )
    result = DiscoveryResult(servers=(server,), warnings=())

    assert location.origin == "local"
    assert result.servers == (server,)
    assert ProcessState.NOT_RUNNING.value == "not_running"
    with pytest.raises(FrozenInstanceError):
        server.url = None  # type: ignore[misc]


@pytest.mark.parametrize(
    ("host", "origin", "gateway", "local_ports", "expected"),
    [
        ("0.0.0.0", "local", None, set(), ("127.0.0.1",)),
        ("", "local", None, set(), ("127.0.0.1",)),
        ("::", "local", None, set(), ("::1",)),
        ("127.0.0.1", "local", None, set(), ("127.0.0.1",)),
        ("192.168.1.20", "local", None, set(), ("192.168.1.20",)),
        (
            "0.0.0.0",
            "windows-host",
            "172.20.0.1",
            set(),
            ("172.20.0.1", "127.0.0.1"),
        ),
        (
            "::",
            "windows-host",
            "203.0.113.1",
            set(),
            ("127.0.0.1",),
        ),
        (
            "192.168.1.20",
            "windows-host",
            "172.20.0.1",
            set(),
            ("192.168.1.20", "172.20.0.1"),
        ),
        (
            "0.0.0.0",
            "windows-host",
            None,
            {2718},
            (),
        ),
    ],
)
def test_candidates_follow_legacy_host_order(
    host: str,
    origin: Origin,
    gateway: str | None,
    local_ports: set[int],
    expected: tuple[str, ...],
) -> None:
    assert (
        _candidate_hosts(
            host=host,
            port=2718,
            origin=origin,
            gateway=gateway,
            live_local_ports=local_ports,
        )
        == expected
    )


def test_registry_files_use_origin_and_filename_order(tmp_path: Path) -> None:
    local_dir = tmp_path / "local"
    windows_dir = tmp_path / "windows"
    local_dir.mkdir()
    windows_dir.mkdir()
    _write_registry(
        local_dir / "b.json",
        server_id="local-b",
        pid=2,
        host="::",
        port=2719,
        base_url="/base",
    )
    _write_registry(
        local_dir / "a.json",
        server_id="local-a",
        pid=1,
    )
    _write_registry(
        windows_dir / "a.json",
        server_id="windows-a",
        pid=3,
        host="192.168.1.20",
        port=2720,
    )
    environment = FakeDiscoveryEnvironment(
        platform="wsl",
        locations=(
            RegistryLocation(windows_dir, "windows-host"),
            RegistryLocation(local_dir, "local"),
        ),
        states={
            (1, "local"): ProcessState.RUNNING,
            (2, "local"): ProcessState.RUNNING,
            (3, "windows-host"): ProcessState.RUNNING,
        },
        reachable_urls={
            "http://127.0.0.1:2718",
            "http://[::1]:2719/base",
            "http://192.168.1.20:2720",
        },
    )

    result = discover_servers(environment)

    assert result == DiscoveryResult(
        servers=(
            PairServer(
                server_id="local-a",
                origin="local",
                url="http://127.0.0.1:2718",
                started_at="2026-08-31T00:00:00+00:00",
                version="0.24.0",
            ),
            PairServer(
                server_id="local-b",
                origin="local",
                url="http://[::1]:2719/base",
                started_at="2026-08-31T00:00:00+00:00",
                version="0.24.0",
            ),
            PairServer(
                server_id="windows-a",
                origin="windows-host",
                url="http://192.168.1.20:2720",
                started_at="2026-08-31T00:00:00+00:00",
                version="0.24.0",
            ),
        ),
        warnings=(),
    )


@pytest.mark.parametrize(
    "record",
    [
        "not json",
        json.dumps({"server_id": "missing-fields"}),
        json.dumps(
            {
                "server_id": "wrong-pid",
                "pid": "4242",
                "host": "127.0.0.1",
                "port": 2718,
                "base_url": "",
                "started_at": "now",
                "version": "0.24.0",
            }
        ),
        json.dumps(
            {
                "server_id": "wrong-port",
                "pid": 4242,
                "host": "127.0.0.1",
                "port": True,
                "base_url": "",
                "started_at": "now",
                "version": "0.24.0",
            }
        ),
    ],
)
def test_registry_skips_invalid_or_untyped_records(
    tmp_path: Path, record: str
) -> None:
    (tmp_path / "entry.json").write_text(record)
    environment = FakeDiscoveryEnvironment(
        locations=(RegistryLocation(tmp_path, "local"),)
    )

    assert discover_servers(environment) == DiscoveryResult((), ())


def test_candidates_do_not_use_wsl_loopback_for_a_live_local_port(
    tmp_path: Path,
) -> None:
    local_dir = tmp_path / "local"
    windows_dir = tmp_path / "windows"
    local_dir.mkdir()
    windows_dir.mkdir()
    _write_registry(local_dir / "local.json", server_id="local", pid=1)
    _write_registry(
        windows_dir / "windows.json",
        server_id="windows",
        pid=2,
        host="0.0.0.0",
    )
    environment = FakeDiscoveryEnvironment(
        platform="wsl",
        locations=(
            RegistryLocation(windows_dir, "windows-host"),
            RegistryLocation(local_dir, "local"),
        ),
        states={
            (1, "local"): ProcessState.RUNNING,
            (2, "windows-host"): ProcessState.RUNNING,
        },
        reachable_urls={"http://127.0.0.1:2718"},
    )

    result = discover_servers(environment)

    assert result.servers == (
        PairServer(
            server_id="local",
            origin="local",
            url="http://127.0.0.1:2718",
            started_at="2026-08-31T00:00:00+00:00",
            version="0.24.0",
        ),
        PairServer(
            server_id="windows",
            origin="windows-host",
            url=None,
            started_at="2026-08-31T00:00:00+00:00",
            version="0.24.0",
        ),
    )
