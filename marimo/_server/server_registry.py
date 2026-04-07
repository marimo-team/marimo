# Copyright 2026 Marimo. All rights reserved.
"""Local discovery registry for running marimo instances.

Each marimo server writes a small JSON file to
``~/.local/state/marimo/servers/<host>_<port>.json`` at startup and
removes it on shutdown.  External tools (e.g. ``list-sessions.sh``)
read these files to discover running instances — no marimo import or
HTTP endpoint is required.

SECURITY: Only instances that have opted into relaxed local access —
started **without** an auth token (``--no-token``) — should be
registered.  See the guard in ``lifespans.server_registry``.
"""

from __future__ import annotations

import atexit
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from marimo import _loggers
from marimo._utils.xdg import marimo_state_dir

LOGGER = _loggers.marimo_logger()

SERVERS_DIR_NAME = "servers"


def _servers_dir() -> Path:
    return marimo_state_dir() / SERVERS_DIR_NAME


def _entry_path(server_id: str) -> Path:
    safe_id = server_id.replace(":", "_").replace("/", "_")
    return _servers_dir() / f"{safe_id}.json"


@dataclass(frozen=True)
class ServerRegistryEntry:
    """Minimal descriptor for a running marimo server.

    SECURITY NOTE: These files live on the local filesystem and are
    readable by any process running as the same user.  Keep the fields
    to the bare minimum needed for discovery — no secrets, no auth
    tokens, no session data.  If you want to add a field, ask whether
    an unauthenticated local process really needs it.
    """

    server_id: str
    pid: int
    host: str
    port: int
    base_url: str
    started_at: str
    version: str

    @staticmethod
    def from_server(
        *,
        host: str,
        port: int,
        base_url: str,
    ) -> ServerRegistryEntry:
        from marimo._version import __version__

        return ServerRegistryEntry(
            server_id=f"{host}:{port}",
            pid=os.getpid(),
            host=host,
            port=port,
            base_url=base_url,
            started_at=datetime.now(timezone.utc).isoformat(),
            version=__version__,
        )


class ServerRegistryWriter:
    """Writes a registry entry on server start, removes on shutdown."""

    def __init__(self, entry: ServerRegistryEntry) -> None:
        self._entry = entry
        self._path = _entry_path(entry.server_id)
        self._registered = False

    def register(self) -> None:
        servers_dir = _servers_dir()
        servers_dir.mkdir(parents=True, exist_ok=True)

        data = json.dumps(asdict(self._entry), indent=2)

        # Atomic write: temp file then rename
        fd, tmp_path = tempfile.mkstemp(dir=str(servers_dir), suffix=".tmp")
        try:
            try:
                os.write(fd, data.encode("utf-8"))
            finally:
                os.close(fd)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, str(self._path))
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        self._registered = True
        atexit.register(self.deregister)
        LOGGER.debug("Registered server: %s", self._path)

    def deregister(self) -> None:
        if not self._registered:
            return
        try:
            self._path.unlink(missing_ok=True)
            LOGGER.debug("Deregistered server: %s", self._path)
        except OSError as e:
            LOGGER.warning(
                "Failed to remove registry entry %s: %s", self._path, e
            )
        finally:
            self._registered = False
