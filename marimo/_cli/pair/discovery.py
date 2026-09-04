# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import csv
import http.client
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from enum import Enum
from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Mapping

PlatformName = Literal["posix", "windows", "wsl"]
Origin = Literal["local", "windows-host", "direct"]


class PairError(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


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


def _detect_platform(
    *,
    sys_platform: str = sys.platform,
    environ: Mapping[str, str] | None = None,
    proc_version: str | None = None,
) -> PlatformName:
    if sys_platform.startswith(("win", "cygwin", "msys")):
        return "windows"
    current_environ = os.environ if environ is None else environ
    if current_environ.get("WSL_DISTRO_NAME"):
        return "wsl"
    if proc_version is None:
        try:
            proc_version = Path("/proc/version").read_text(encoding="utf-8")
        except OSError:
            proc_version = ""
    if "microsoft" in proc_version.lower():
        return "wsl"
    return "posix"


class SystemDiscoveryEnvironment:
    def __init__(
        self,
        *,
        platform: PlatformName | None = None,
        home: Path | None = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._environ = dict(os.environ if environ is None else environ)
        self._home = Path.home() if home is None else home
        self.platform = platform or _detect_platform(environ=self._environ)
        self._tasklist_loaded = False
        self._windows_pids: frozenset[int] | None = None
        self._gateway_loaded = False
        self._gateway: str | None = None

    def registry_locations(self) -> tuple[RegistryLocation, ...]:
        if self.platform == "windows":
            local = self._home / ".marimo" / "servers"
        else:
            state_home = self._environ.get("XDG_STATE_HOME", "").strip()
            state_root = (
                Path(state_home)
                if state_home
                else self._home / ".local" / "state"
            )
            local = state_root / "marimo" / "servers"

        locations = [RegistryLocation(local, "local")]
        if self.platform == "wsl":
            windows_home = self._windows_home()
            if windows_home is not None:
                locations.append(
                    RegistryLocation(
                        windows_home / ".marimo" / "servers",
                        "windows-host",
                    )
                )
        return tuple(locations)

    def process_state(self, pid: int, origin: Origin) -> ProcessState:
        if pid <= 0:
            return ProcessState.UNKNOWN
        if origin == "windows-host" or self.platform == "windows":
            windows_pids = self._load_windows_pids()
            if windows_pids is None:
                return ProcessState.UNKNOWN
            if pid in windows_pids:
                return ProcessState.RUNNING
            return ProcessState.NOT_RUNNING

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return ProcessState.NOT_RUNNING
        except PermissionError:
            return ProcessState.RUNNING
        except OSError:
            return ProcessState.UNKNOWN
        return ProcessState.RUNNING

    def gateway(self) -> str | None:
        if self._gateway_loaded:
            return self._gateway
        self._gateway_loaded = True
        if self.platform != "wsl":
            return None

        executable = shutil.which("ip", path=self._environ.get("PATH", ""))
        if executable is not None:
            result = self._run((executable, "route", "show", "default"))
            if result is not None:
                fields = result.stdout.split()
                if len(fields) >= 3 and fields[0] == "default":
                    self._gateway = fields[2]
                    return self._gateway

        try:
            rows = Path("/proc/net/route").read_text(encoding="utf-8")
        except OSError:
            return None
        for row in rows.splitlines():
            fields = row.split()
            if len(fields) < 8 or fields[1] != "00000000":
                continue
            if fields[7] != "00000000" or len(fields[2]) != 8:
                continue
            try:
                octets = bytes.fromhex(fields[2])
            except ValueError:
                continue
            self._gateway = ".".join(str(part) for part in reversed(octets))
            return self._gateway
        return None

    def answers_marimo(self, url: str) -> bool:
        try:
            parsed = urlsplit(url)
            if parsed.scheme != "http" or parsed.hostname is None:
                return False
            connection = http.client.HTTPConnection(
                parsed.hostname,
                parsed.port,
                timeout=1.0,
            )
        except ValueError:
            return False

        deadline = time.monotonic() + 2.0
        health_path = f"{parsed.path.rstrip('/')}/health"
        try:
            connection.connect()
            if connection.sock is not None:
                remaining = max(deadline - time.monotonic(), 0.001)
                connection.sock.settimeout(remaining)
            connection.request("GET", health_path)
            response = connection.getresponse()
            data = json.loads(response.read())
            return (
                response.status < 400
                and isinstance(data, dict)
                and data.get("status") == "healthy"
            )
        except (
            OSError,
            ValueError,
            UnicodeDecodeError,
            http.client.HTTPException,
            json.JSONDecodeError,
        ):
            return False
        finally:
            connection.close()

    def _run(
        self,
        command: tuple[str, ...],
        *,
        env_overrides: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str] | None:
        command_environ = {
            **self._environ,
            **({} if env_overrides is None else env_overrides),
        }
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
                env=command_environ,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result if result.returncode == 0 else None

    def _windows_executable(self, name: str) -> str | None:
        executable = shutil.which(name, path=self._environ.get("PATH", ""))
        if executable is not None:
            return executable
        if self.platform != "wsl":
            return None
        wslpath = shutil.which("wslpath", path=self._environ.get("PATH", ""))
        if wslpath is None:
            return None
        result = self._run((wslpath, "-u", "C:\\Windows\\System32"))
        if result is None:
            return None
        candidate = Path(result.stdout.strip()) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
        return None

    def _windows_home(self) -> Path | None:
        cmd = self._windows_executable("cmd.exe")
        wslpath = shutil.which("wslpath", path=self._environ.get("PATH", ""))
        if cmd is None or wslpath is None:
            return None
        result = self._run((cmd, "/c", "echo %USERPROFILE%"))
        if result is None:
            return None
        profile = result.stdout.replace("\r", "").strip()
        if not profile or profile == "%USERPROFILE%":
            return None
        result = self._run((wslpath, "-u", profile))
        if result is None or not result.stdout.strip():
            return None
        return Path(result.stdout.strip())

    def _load_windows_pids(self) -> frozenset[int] | None:
        if self._tasklist_loaded:
            return self._windows_pids
        self._tasklist_loaded = True
        tasklist = self._windows_executable("tasklist.exe")
        if tasklist is None:
            return None
        result = self._run(
            (tasklist, _TASKLIST_FORMAT_OPTION, "CSV", "/NH"),
            env_overrides={
                "MSYS_NO_PATHCONV": "1",
                "MSYS2_ARG_CONV_EXCL": "*",
            },
        )
        if result is None:
            return None
        pids = {
            int(row[1])
            for row in csv.reader(result.stdout.splitlines())
            if len(row) >= 2 and row[1].isdigit()
        }
        if not pids:
            return None
        self._windows_pids = frozenset(pids)
        return self._windows_pids


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
_TASKLIST_FORMAT_OPTION = "/" + "F" + "O"


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


def _unreachable_warning(
    record: _RegistryRecord,
    *,
    origin: Origin,
    environment: DiscoveryEnvironment,
) -> str:
    reused_pid = (
        f"If marimo is no longer running, PID {record.pid} may belong to "
        "an unrelated process that reused the id."
    )
    if origin != "windows-host":
        return (
            f"{record.server_id} is registered (PID {record.pid}) but "
            f"nothing answers there. {reused_pid}"
        )

    prefix = (
        f"{record.server_id} is running on the Windows host "
        f"(PID {record.pid}) but answered at no address reachable from WSL."
    )
    gateway = environment.gateway()
    if record.host in ("0.0.0.0", "::"):
        guidance = (
            f" It is bound to {record.host}, so the Windows firewall is the "
            f"likely cause. Allow inbound TCP {record.port} on the vEthernet "
            f"(WSL) adapter{f' at {gateway}' if gateway else ''}."
        )
    else:
        guidance = (
            f" WSL NAT cannot reach a service bound to {record.host} on the "
            "host. Restart marimo with --host 0.0.0.0 or use mirrored "
            "networking."
        )
    return f"{prefix}{guidance} {reused_pid}"


def discover_servers(
    environment: DiscoveryEnvironment | None = None,
) -> DiscoveryResult:
    if environment is None:
        environment = SystemDiscoveryEnvironment()

    locations = sorted(
        enumerate(environment.registry_locations()),
        key=lambda item: (item[1].origin != "local", item[0]),
    )
    servers: list[PairServer] = []
    warnings: list[str] = []
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
                if state is ProcessState.NOT_RUNNING:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        pass
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
            if url is None:
                warnings.append(
                    _unreachable_warning(
                        record,
                        origin=location.origin,
                        environment=environment,
                    )
                )
    return DiscoveryResult(
        servers=tuple(servers),
        warnings=tuple(warnings),
    )
