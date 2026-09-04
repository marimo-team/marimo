# Copyright 2026 Marimo. All rights reserved.
"""Catalog and operation state for a local discovery publisher."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import uuid4, uuid5

from marimo import _loggers
from marimo._messaging.msgspec_encoder import encode_json_bytes
from marimo._server.discovery.models import (
    Catalog,
    InstanceRecord,
    NotebookSummary,
    OpenNotebookResponse,
    ProjectSummary,
    SessionStatus,
    SessionSummary,
)
from marimo._server.workspace import NEW_FILE, flatten_files
from marimo._session.model import SessionMode
from marimo._session.types import KernelState
from marimo._utils.asyncio_utils import cancel_and_wait

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Iterator, Sequence

    from marimo._server.models.files import FileInfo
    from marimo._server.session_manager import SessionManager
    from marimo._session.types import Session

DISCOVERY_API_PATH = "/api/marimo/v1"
DISCOVERY_OPERATIONS = [
    "catalog.watch",
    "notebook.open",
    "session.execute",
]
DISCOVERY_ENABLED_ENV = "MARIMO_DISCOVERY_ENABLED"
DISCOVERY_KIND_ENV = "MARIMO_DISCOVERY_KIND"
DISCOVERY_NAME_ENV = "MARIMO_DISCOVERY_NAME"
_BROWSER_TOKEN_TTL = timedelta(seconds=60)
_POLL_INTERVAL_SECONDS = 1.0
LOGGER = _loggers.marimo_logger()


@dataclass(frozen=True)
class _NotebookTarget:
    file_key: str
    openable: bool


@dataclass(frozen=True)
class _BrowserToken:
    file_key: str
    expires_at: datetime | None


class DiscoveryManager:
    """Owns one publisher's record, catalog, and transient browser tokens."""

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
        self._browser_tokens: dict[str, _BrowserToken] = {}
        self._subscribers: set[asyncio.Queue[None]] = set()
        self._watch_task: asyncio.Task[None] | None = None

    async def close(self) -> None:
        if self._watch_task is not None:
            task = self._watch_task
            self._watch_task = None
            await cancel_and_wait(task)
        self._subscribers.clear()
        self._browser_tokens.clear()

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

    async def open_notebook(self, notebook_id: str) -> OpenNotebookResponse:
        # Refresh first so IDs for files added since the previous request work.
        _, targets = await self._snapshot()
        target = targets.get(notebook_id)
        if target is None:
            raise KeyError("Notebook not found")
        if not target.openable:
            raise RuntimeError("Notebook is not openable")

        query: dict[str, str] = {"file": target.file_key}
        if str(self.session_manager.auth_token):
            query["access_token"] = self.issue_browser_token(target.file_key)
        return OpenNotebookResponse(
            uri=f"{self.browser_url}/?{urlencode(query)}"
        )

    def issue_browser_token(self, file_key: str) -> str:
        return self._issue_browser_token(
            file_key, datetime.now(timezone.utc) + _BROWSER_TOKEN_TTL
        )

    def _issue_browser_token(
        self, file_key: str, expires_at: datetime | None
    ) -> str:
        self._purge_browser_tokens()
        token = secrets.token_urlsafe(32)
        self._browser_tokens[token] = _BrowserToken(
            file_key=file_key,
            expires_at=expires_at,
        )
        return token

    def consume_browser_token(
        self, token: str, file_key: str | None
    ) -> str | None:
        self._purge_browser_tokens()
        entry = self._browser_tokens.get(token)
        if entry is None:
            return None
        if file_key is not None and entry.file_key != file_key:
            return None
        del self._browser_tokens[token]
        return entry.file_key

    @contextmanager
    def execution_credentials(
        self, session: Session
    ) -> Iterator[tuple[str, str]]:
        """Keep screenshot bootstrap credentials valid until execution ends."""
        path = session.app_file_manager.path
        file_key = (
            session.initialization_id
            if path is None
            else self._file_key(
                path, self._relative_path(path, self._project_root())
            )
        )
        server_url = f"{self.browser_url}/?{urlencode({'file': file_key})}"
        auth_token = ""
        if str(self.session_manager.auth_token):
            # Queueing or running code may take arbitrarily long. The response
            # owns this token's lifetime; browser login still consumes it once.
            auth_token = self._issue_browser_token(file_key, expires_at=None)
        try:
            yield server_url, auth_token
        finally:
            self._browser_tokens.pop(auth_token, None)

    async def watch(self) -> AsyncGenerator[str, None]:
        from marimo._server.sse import format_sse_event

        queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
        self._subscribers.add(queue)
        if self._watch_task is None:
            self._watch_task = asyncio.create_task(
                self._watch_loop(), name="discovery.catalog.watch"
            )
        queue.put_nowait(None)
        try:
            while True:
                await queue.get()
                yield format_sse_event("{}", event="catalog.changed")
        finally:
            self._subscribers.discard(queue)
            if not self._subscribers and self._watch_task is not None:
                task = self._watch_task
                self._watch_task = None
                await cancel_and_wait(task)

    async def _watch_loop(self) -> None:
        last_fingerprint: bytes | None = None
        while self._subscribers:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            try:
                fingerprint = await self._fingerprint()
            except Exception as e:
                LOGGER.warning(
                    "Failed to refresh the local discovery catalog: %s", e
                )
                continue
            if fingerprint == last_fingerprint:
                continue
            last_fingerprint = fingerprint
            for queue in tuple(self._subscribers):
                if queue.empty():
                    queue.put_nowait(None)

    async def _fingerprint(self) -> bytes:
        return hashlib.sha256(encode_json_bytes(await self.catalog())).digest()

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

    def _purge_browser_tokens(self) -> None:
        now = datetime.now(timezone.utc)
        self._browser_tokens = {
            token: entry
            for token, entry in self._browser_tokens.items()
            if entry.expires_at is None or entry.expires_at > now
        }


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
