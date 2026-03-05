# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import atexit
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pathlib import Path

from marimo import _loggers
from marimo._utils.xdg import marimo_state_dir

LOGGER = _loggers.marimo_logger()

SESSIONS_DIR_NAME = "sessions"


def _sessions_dir() -> Path:
    return marimo_state_dir() / SESSIONS_DIR_NAME


def _entry_path(server_id: str) -> Path:
    # Replace colons/slashes with underscores for safe filenames
    safe_id = server_id.replace(":", "_").replace("/", "_")
    return _sessions_dir() / f"{safe_id}.json"


@dataclass(frozen=True)
class SessionRegistryEntry:
    server_id: str
    pid: int
    host: str
    port: int
    base_url: str
    auth_token: str
    mode: str
    started_at: str
    notebook_path: Optional[str]
    mcp_enabled: bool
    version: str


class SessionRegistryWriter:
    """Writes a registry entry on server start, removes on shutdown."""

    def __init__(self, entry: SessionRegistryEntry) -> None:
        self._entry = entry
        self._path = _entry_path(entry.server_id)
        self._registered = False

    def register(self) -> None:
        sessions_dir = _sessions_dir()
        sessions_dir.mkdir(parents=True, exist_ok=True)

        data = json.dumps(asdict(self._entry), indent=2)

        # Atomic write: write to temp file then rename
        fd, tmp_path = tempfile.mkstemp(dir=str(sessions_dir), suffix=".tmp")
        try:
            os.write(fd, data.encode("utf-8"))
            os.close(fd)
            os.chmod(tmp_path, 0o600)
            os.rename(tmp_path, str(self._path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        self._registered = True
        atexit.register(self.deregister)
        LOGGER.debug("Registered session registry entry: %s", self._path)

    def deregister(self) -> None:
        if not self._registered:
            return
        try:
            self._path.unlink(missing_ok=True)
            LOGGER.debug("Deregistered session registry entry: %s", self._path)
        except OSError as e:
            LOGGER.warning(
                "Failed to remove registry entry %s: %s", self._path, e
            )
        finally:
            self._registered = False


class SessionRegistryReader:
    """Reads and validates session registry entries."""

    @staticmethod
    def read_all() -> list[SessionRegistryEntry]:
        sessions_dir = _sessions_dir()
        if not sessions_dir.exists():
            return []

        entries: list[SessionRegistryEntry] = []
        for path in sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                entry = SessionRegistryEntry(**data)

                # Validate PID is still alive
                if not _is_pid_alive(entry.pid):
                    LOGGER.debug(
                        "Removing stale registry entry (PID %d): %s",
                        entry.pid,
                        path,
                    )
                    path.unlink(missing_ok=True)
                    continue

                entries.append(entry)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                LOGGER.warning(
                    "Skipping invalid registry entry %s: %s", path, e
                )
                # Remove corrupted entries
                path.unlink(missing_ok=True)

        return entries

    @staticmethod
    def find_by_port(port: int) -> Optional[SessionRegistryEntry]:
        for entry in SessionRegistryReader.read_all():
            if entry.port == port:
                return entry
        return None

    @staticmethod
    def find_by_server_id(
        server_id: str,
    ) -> Optional[SessionRegistryEntry]:
        for entry in SessionRegistryReader.read_all():
            if entry.server_id == server_id:
                return entry
        return None


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we don't have permission to signal it
        return True
    except OSError:
        return False


def create_registry_entry(
    *,
    host: str,
    port: int,
    base_url: str,
    auth_token: str,
    mode: str,
    notebook_path: Optional[str],
    mcp_enabled: bool,
) -> SessionRegistryEntry:
    from marimo._version import __version__

    server_id = f"{host}:{port}"
    return SessionRegistryEntry(
        server_id=server_id,
        pid=os.getpid(),
        host=host,
        port=port,
        base_url=base_url,
        auth_token=auth_token,
        mode=mode,
        started_at=datetime.now(timezone.utc).isoformat(),
        notebook_path=notebook_path,
        mcp_enabled=mcp_enabled,
        version=__version__,
    )
