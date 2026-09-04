# Copyright 2026 Marimo. All rights reserved.
"""Catalog and operation state for a local discovery publisher."""

from __future__ import annotations

import asyncio
import hmac
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4, uuid5

from marimo import _loggers
from marimo._server.discovery.models import (
    Catalog,
    InstanceRecord,
    NotebookSummary,
    ProjectSummary,
    SessionStatus,
    SessionSummary,
)
from marimo._server.workspace import NEW_FILE, flatten_files
from marimo._session.model import SessionMode
from marimo._session.types import KernelState

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._server.models.files import FileInfo
    from marimo._server.session_manager import SessionManager
    from marimo._session.types import Session

DISCOVERY_API_PATH = "/api/marimo/v1"
DISCOVERY_OPERATIONS: list[str] = []
DISCOVERY_ENABLED_ENV = "MARIMO_DISCOVERY_ENABLED"
DISCOVERY_KIND_ENV = "MARIMO_DISCOVERY_KIND"
DISCOVERY_NAME_ENV = "MARIMO_DISCOVERY_NAME"
LOGGER = _loggers.marimo_logger()


@dataclass(frozen=True)
class _NotebookTarget:
    file_key: str
    openable: bool


class DiscoveryManager:
    """Owns one publisher's record and notebook catalog."""

    def __init__(
        self,
        *,
        session_manager: SessionManager,
        browser_url: str,
        kind: str,
        name: str,
    ) -> None:
        self.instance_id = uuid4()
        self.token = secrets.token_urlsafe(32)
        self.started_at = datetime.now(timezone.utc)
        self.session_manager = session_manager
        self.browser_url = browser_url.rstrip("/")
        self.record = InstanceRecord(
            id=self.instance_id,
            kind=kind,
            name=name,
            pid=os.getpid(),
            started_at=self.started_at,
            url=f"{self.browser_url}{DISCOVERY_API_PATH}",
            token=self.token,
        )
        self._catalog_lock = asyncio.Lock()

    def is_authorized(self, token: str) -> bool:
        return hmac.compare_digest(token, self.token)

    async def catalog(self) -> Catalog:
        catalog, _ = await self._snapshot()
        return catalog

    async def _snapshot(self) -> tuple[Catalog, dict[str, _NotebookTarget]]:
        async with self._catalog_lock:
            self.session_manager.workspace.invalidate()
            files = await asyncio.to_thread(
                lambda: list(
                    flatten_files(self.session_manager.workspace.files)
                )
            )
            return self._build_catalog(files)

    def _build_catalog(
        self, files: Sequence[FileInfo]
    ) -> tuple[Catalog, dict[str, _NotebookTarget]]:
        workspace = self.session_manager.workspace
        root = self._project_root()
        project_key = root or "untitled"
        project_id = self._stable_id(f"project:{project_key}")
        project_name = Path(root).name if root else "Untitled"

        sessions_by_path: dict[str | None, list[tuple[str, Session]]] = {}
        for session_id, session in self.session_manager.sessions.items():
            path = session.app_file_manager.path
            normalized = self._normalize_path(path) if path else None
            sessions_by_path.setdefault(normalized, []).append(
                (str(session_id), session)
            )

        notebooks: list[NotebookSummary] = []
        targets: dict[str, _NotebookTarget] = {}

        def add_notebook(
            identity: str,
            path: str | None,
            title: str,
            session_pairs: list[tuple[str, Session]],
            untitled_key: str = NEW_FILE,
        ) -> None:
            notebook_id = self._stable_id(f"notebook:{identity}")
            relative_path = self._relative_path(path, root)
            if path is not None:
                openable = Path(path).is_file()
                file_key = self._file_key(path, relative_path)
            else:
                openable = len(session_pairs) <= 1
                file_key = (
                    session_pairs[0][1].initialization_id
                    if len(session_pairs) == 1
                    else untitled_key
                )
            notebooks.append(
                NotebookSummary(
                    id=notebook_id,
                    title=title,
                    openable=openable,
                    path=relative_path,
                    updated_at=self._path_updated_at(path),
                    sessions=self._session_summaries(session_pairs),
                )
            )
            targets[notebook_id] = _NotebookTarget(file_key, openable)

        represented_paths: set[str | None] = set()
        for item in files:
            if not item.is_marimo_file:
                continue
            absolute_path, _ = self._file_paths(item.path, root)
            if not Path(absolute_path).is_file():
                continue
            normalized = self._normalize_path(absolute_path)
            represented_paths.add(normalized)
            session_pairs = sessions_by_path.get(normalized, [])
            add_notebook(normalized, absolute_path, item.name, session_pairs)

        unique_key = workspace.get_unique_file_key()
        if unique_key is not None and unique_key.startswith(NEW_FILE):
            session_pairs = sessions_by_path.get(None, [])
            add_notebook(
                unique_key, None, "Untitled", session_pairs, unique_key
            )
            represented_paths.add(None)

        # A newly created or renamed notebook can have a live session before a
        # directory rescan includes it. Keep the catalog a complete snapshot.
        for normalized, session_pairs in sessions_by_path.items():
            if normalized in represented_paths:
                continue
            first_session = session_pairs[0][1]
            path = first_session.app_file_manager.path
            identity = normalized or first_session.initialization_id
            add_notebook(
                identity,
                path,
                Path(path).name if path else "Untitled",
                session_pairs,
                first_session.initialization_id,
            )

        notebooks.sort(key=lambda notebook: (notebook.path or "", notebook.id))
        return Catalog(
            instance_id=self.instance_id,
            operations=list(DISCOVERY_OPERATIONS),
            projects=[
                ProjectSummary(
                    id=project_id,
                    name=project_name,
                    root=root,
                    truncated=workspace.truncated,
                    notebooks=notebooks,
                )
            ],
        ), targets

    def _project_root(self) -> str | None:
        workspace = self.session_manager.workspace
        if workspace.directory is not None:
            return str(Path(workspace.directory).absolute())
        single = workspace.single_file()
        if single is not None:
            return str(Path(single.path).absolute().parent)
        return None

    def _file_paths(
        self, path: str, root: str | None
    ) -> tuple[str, str | None]:
        candidate = Path(path)
        absolute = (
            candidate
            if candidate.is_absolute()
            else Path(root or ".") / candidate
        )
        absolute_path = str(absolute.absolute())
        return absolute_path, self._relative_path(absolute_path, root)

    def _relative_path(self, path: str | None, root: str | None) -> str | None:
        if path is None or root is None:
            return None
        try:
            return str(
                Path(path).absolute().relative_to(Path(root).absolute())
            )
        except ValueError:
            return None

    def _file_key(self, absolute_path: str, relative_path: str | None) -> str:
        if self.session_manager.workspace.directory is not None:
            return relative_path or absolute_path
        return absolute_path

    def _session_summaries(
        self, pairs: list[tuple[str, Session]]
    ) -> list[SessionSummary]:
        from marimo._version import __version__

        summaries = [
            SessionSummary(
                session_id=session_id,
                status=self._session_status(session),
                mode=(
                    "edit"
                    if self.session_manager.mode is SessionMode.EDIT
                    else "app"
                ),
                started_at=getattr(session, "started_at", self.started_at),
                marimo_version=__version__,
            )
            for session_id, session in pairs
        ]
        summaries.sort(key=lambda summary: summary.session_id)
        return summaries

    @staticmethod
    def _session_status(session: Session) -> SessionStatus:
        state = session.kernel_state()
        if state is KernelState.NOT_STARTED:
            return "starting"
        if state is KernelState.RUNNING:
            return "running"
        exit_info = session.kernel_exit_info()
        if exit_info is not None and exit_info.exitcode not in (None, 0):
            return "failed"
        return "terminated"

    def _stable_id(self, value: str) -> str:
        return str(uuid5(self.instance_id, value))

    @staticmethod
    def _normalize_path(path: str) -> str:
        return os.path.normcase(os.path.abspath(path))

    @staticmethod
    def _datetime_from_timestamp(value: float | None) -> datetime | None:
        if value is None:
            return None
        return datetime.fromtimestamp(value, tz=timezone.utc)

    @classmethod
    def _path_updated_at(cls, path: str | None) -> datetime | None:
        if path is None:
            return None
        try:
            return cls._datetime_from_timestamp(os.path.getmtime(path))
        except OSError:
            return None


def build_discovery_manager(
    *,
    session_manager: SessionManager,
    host: str,
    port: int,
    base_url: str,
) -> DiscoveryManager | None:
    """Create a publisher for binds reachable at a protocol loopback URL."""
    import ipaddress

    if (
        session_manager.mode is not SessionMode.EDIT
        or os.environ.get(DISCOVERY_ENABLED_ENV) == "0"
    ):
        return None

    normalized_host = host.strip("[]").split("%", 1)[0]
    if normalized_host.lower() == "localhost":
        advertised_host = "127.0.0.1"
    else:
        try:
            address = ipaddress.ip_address(normalized_host)
        except ValueError:
            return None
        mapped = (
            address.ipv4_mapped
            if isinstance(address, ipaddress.IPv6Address)
            else None
        )
        # The protocol only permits 127.0.0.1 and ::1 in advertised URLs.
        # Other loopback binds need not be reachable at either address.
        if (
            mapped is not None
            and str(mapped) == "127.0.0.1"
            or address.version == 4
            and (str(address) == "127.0.0.1" or address.is_unspecified)
        ):
            advertised_host = "127.0.0.1"
        elif address.version == 6 and (
            str(address) == "::1" or address.is_unspecified
        ):
            advertised_host = "[::1]"
        else:
            return None

    prefix = base_url.rstrip("/")
    browser_url = f"http://{advertised_host}:{port}{prefix}"
    return DiscoveryManager(
        session_manager=session_manager,
        browser_url=browser_url,
        kind=os.environ.get(DISCOVERY_KIND_ENV) or "marimo",
        name=os.environ.get(DISCOVERY_NAME_ENV) or "marimo CLI",
    )
