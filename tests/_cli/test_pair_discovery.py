# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import threading
from dataclasses import FrozenInstanceError, asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from marimo._cli.pair.discovery import (
    DiscoveryResult,
    Origin,
    PairServer,
    PlatformName,
    ProcessState,
    RegistryLocation,
    SystemDiscoveryEnvironment,
    _candidate_hosts,
    _detect_platform,
    discover_servers,
)


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


def _write_executable(path: Path, body: str) -> None:
    path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    path.chmod(0o755)


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


@pytest.mark.parametrize(
    ("sys_platform", "environ", "proc_version", "expected"),
    [
        ("darwin", {}, "Darwin", "posix"),
        ("win32", {}, "", "windows"),
        ("cygwin", {}, "", "windows"),
        ("linux", {"WSL_DISTRO_NAME": "Ubuntu"}, "Linux", "wsl"),
        ("linux", {}, "Linux microsoft-standard-WSL2", "wsl"),
    ],
)
def test_detect_platform(
    sys_platform: str,
    environ: dict[str, str],
    proc_version: str,
    expected: PlatformName,
) -> None:
    assert (
        _detect_platform(
            sys_platform=sys_platform,
            environ=environ,
            proc_version=proc_version,
        )
        == expected
    )


def test_registry_locations_follow_platform_conventions(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    state = tmp_path / "state"

    posix = SystemDiscoveryEnvironment(
        platform="posix",
        home=home,
        environ={"XDG_STATE_HOME": str(state)},
    )
    windows = SystemDiscoveryEnvironment(
        platform="windows",
        home=home,
        environ={},
    )

    assert posix.registry_locations() == (
        RegistryLocation(state / "marimo" / "servers", "local"),
    )
    assert SystemDiscoveryEnvironment(
        platform="posix",
        home=home,
        environ={},
    ).registry_locations() == (
        RegistryLocation(home / ".local/state/marimo/servers", "local"),
    )
    assert windows.registry_locations() == (
        RegistryLocation(home / ".marimo" / "servers", "local"),
    )


def test_wsl_registry_locations_include_windows_profile(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    windows_home = tmp_path / "windows-home"
    _write_executable(bin_dir / "cmd.exe", "printf 'C:\\\\Users\\\\Ada\\r\\n'")
    _write_executable(
        bin_dir / "wslpath",
        "printf '%s\\n' \"$FAKE_WINDOWS_HOME\"",
    )
    environment = SystemDiscoveryEnvironment(
        platform="wsl",
        home=tmp_path / "linux-home",
        environ={
            "PATH": str(bin_dir),
            "FAKE_WINDOWS_HOME": str(windows_home),
        },
    )

    assert environment.registry_locations() == (
        RegistryLocation(
            tmp_path / "linux-home" / ".local/state/marimo/servers",
            "local",
        ),
        RegistryLocation(windows_home / ".marimo/servers", "windows-host"),
    )


def test_process_state_distinguishes_all_three_states(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "tasklist.exe",
        '[ "$MSYS_NO_PATHCONV" = 1 ] || exit 1\n'
        "[ \"$MSYS2_ARG_CONV_EXCL\" = '*' ] || exit 1\n"
        '[ "$1 $2 $3" = "/F${EMPTY:-}O CSV /NH" ] || exit 1\n'
        'printf \'"python.exe","101","Console","1","10 K"\\n\'',
    )
    environment = SystemDiscoveryEnvironment(
        platform="wsl",
        home=tmp_path,
        environ={"PATH": str(bin_dir)},
    )

    assert (
        environment.process_state(os.getpid(), "local") is ProcessState.RUNNING
    )
    assert (
        environment.process_state(99_999_999, "local")
        is ProcessState.NOT_RUNNING
    )
    assert (
        environment.process_state(101, "windows-host") is ProcessState.RUNNING
    )
    assert (
        environment.process_state(202, "windows-host")
        is ProcessState.NOT_RUNNING
    )
    assert environment.process_state(0, "local") is ProcessState.UNKNOWN

    unavailable = SystemDiscoveryEnvironment(
        platform="wsl",
        home=tmp_path,
        environ={"PATH": ""},
    )
    assert (
        unavailable.process_state(101, "windows-host") is ProcessState.UNKNOWN
    )


def test_health_check_requires_a_healthy_marimo_response() -> None:
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = (
                b'{"status":"healthy"}'
                if self.path == "/base/health"
                else b'{"status":"other"}'
            )
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *args: object) -> None:
            del args

    server = ThreadingHTTPServer(("127.0.0.1", 0), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        environment = SystemDiscoveryEnvironment(platform="posix")
        base = f"http://127.0.0.1:{server.server_port}"
        assert environment.answers_marimo(f"{base}/base")
        assert not environment.answers_marimo(base)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_discovery_matches_fixture_and_removes_only_stale_entries(
    tmp_path: Path,
) -> None:
    fixtures = Path(__file__).parent / "fixtures" / "marimo_pair_v0_0_19"
    registry_dir = tmp_path / "servers"
    registry_dir.mkdir()
    live_path = registry_dir / "a-live.json"
    live_path.write_text(
        (fixtures / "registry.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    stale_path = registry_dir / "b-stale.json"
    _write_registry(stale_path, server_id="stale", pid=2, port=2719)
    unknown_path = registry_dir / "c-unknown.json"
    _write_registry(unknown_path, server_id="unknown", pid=3, port=2720)
    environment = FakeDiscoveryEnvironment(
        locations=(RegistryLocation(registry_dir, "local"),),
        states={
            (4242, "local"): ProcessState.RUNNING,
            (2, "local"): ProcessState.NOT_RUNNING,
            (3, "local"): ProcessState.UNKNOWN,
        },
        reachable_urls={"http://127.0.0.1:2718"},
    )

    result = discover_servers(environment)

    expected = json.loads(
        (fixtures / "discover-output.json").read_text(encoding="utf-8")
    )
    assert [asdict(server) for server in result.servers] == expected
    assert live_path.exists()
    assert not stale_path.exists()
    assert unknown_path.exists()


def test_unreachable_running_server_produces_actionable_wsl_warning(
    tmp_path: Path,
) -> None:
    _write_registry(
        tmp_path / "server.json",
        server_id="windows-server",
        pid=101,
        host="0.0.0.0",
    )
    environment = FakeDiscoveryEnvironment(
        platform="wsl",
        locations=(RegistryLocation(tmp_path, "windows-host"),),
        states={(101, "windows-host"): ProcessState.RUNNING},
        gateway_address="172.20.0.1",
    )

    result = discover_servers(environment)

    assert result.servers[0].url is None
    warning = "\n".join(result.warnings)
    assert "Windows host" in warning
    assert "firewall" in warning
    assert "2718" in warning
