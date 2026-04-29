# Copyright 2026 Marimo. All rights reserved.
"""Dataflow session management.

Architecture:

- `DataflowFileBundle`: per file. Owns the persistent `DataflowRuntime` for
  that notebook plus the cached `DataflowSchema`. The cache key is the
  notebook's source-code hash, so schemas auto-invalidate on file edits.
- `DataflowSessionManager`: registry keyed on file path. Lazily creates
  bundles on demand and garbage-collects ones that haven't been used in a
  while.
- `DataflowSession`: lightweight per-client wrapper carrying a session id and
  recency metadata. Phase 2.x runs all clients through a single shared
  runtime per file (serialized via the runtime's lock); Phase 3 will split
  this into per-client isolation when editor parity arrives.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import TYPE_CHECKING, Any

from marimo._dataflow.runtime import DataflowRuntime
from marimo._dataflow.schema import compute_dataflow_schema

if TYPE_CHECKING:
    from marimo._ast.app import InternalApp
    from marimo._dataflow.protocol import DataflowEvent, DataflowSchema


class DataflowFileBundle:
    """Per-notebook state: persistent runtime + cached schema."""

    def __init__(self, app: InternalApp) -> None:
        self.app = app
        self.runtime = DataflowRuntime(app)
        self._cached_schema: DataflowSchema | None = None
        self._cached_schema_hash: str | None = None
        self._schema_lock = asyncio.Lock()
        self.created_at = time.time()
        self.last_accessed = time.time()

    def _content_hash(self) -> str:
        """SHA-256 of the concatenated cell sources, for schema cache keying."""
        h = hashlib.sha256()
        for cell_id in self.app.cell_manager.cell_ids():
            cell_data = self.app.cell_manager.cell_data_at(cell_id)
            cell = cell_data.cell
            if cell is not None:
                h.update(cell._cell.code.encode("utf-8"))
                h.update(b"\x00")
        return h.hexdigest()

    async def get_schema(self) -> DataflowSchema:
        """Return the cached schema, computing it on miss.

        The first call runs the notebook with defaults (cold start). Hits
        thereafter are O(1) until the file content changes.
        """
        current_hash = self._content_hash()
        if (
            self._cached_schema is not None
            and self._cached_schema_hash == current_hash
        ):
            self.last_accessed = time.time()
            return self._cached_schema

        async with self._schema_lock:
            if (
                self._cached_schema is not None
                and self._cached_schema_hash == current_hash
            ):
                self.last_accessed = time.time()
                return self._cached_schema

            loop = asyncio.get_event_loop()
            schema = await loop.run_in_executor(
                self.runtime._worker,
                compute_dataflow_schema,
                self.runtime,
            )
            self._cached_schema = schema
            self._cached_schema_hash = current_hash
            self.last_accessed = time.time()
            return schema

    async def run(
        self,
        inputs: dict[str, Any],
        subscribed: set[str],
    ) -> list[DataflowEvent]:
        self.last_accessed = time.time()
        return await self.runtime.apply_inputs_and_run(inputs, subscribed)


class DataflowSession:
    """Per-client session metadata (Phase 2.x: thin wrapper).

    Holds a session id and recency for routing/observability. The actual
    runtime is the file bundle's runtime, shared across all sessions of that
    file. A future iteration will separate per-client state.
    """

    def __init__(
        self,
        bundle: DataflowFileBundle,
        session_id: str,
    ) -> None:
        self.session_id = session_id
        self.bundle = bundle
        self.created_at = time.time()
        self.last_accessed = time.time()

    @property
    def app(self) -> InternalApp:
        return self.bundle.app

    async def get_schema(self) -> DataflowSchema:
        self.last_accessed = time.time()
        return await self.bundle.get_schema()

    async def run(
        self,
        inputs: dict[str, Any],
        subscribed: set[str],
    ) -> list[DataflowEvent]:
        self.last_accessed = time.time()
        return await self.bundle.run(inputs, subscribed)


class DataflowSessionManager:
    """One manager per file (or per server). Holds the bundle and sessions."""

    def __init__(self, app: InternalApp, ttl_seconds: float = 600) -> None:
        self._bundle = DataflowFileBundle(app)
        self._sessions: dict[str, DataflowSession] = {}
        self._ttl = ttl_seconds

    @property
    def app(self) -> InternalApp:
        return self._bundle.app

    @property
    def bundle(self) -> DataflowFileBundle:
        return self._bundle

    async def get_schema(self) -> DataflowSchema:
        return await self._bundle.get_schema()

    def get_or_create(self, session_id: str) -> DataflowSession:
        self._gc()
        if session_id not in self._sessions:
            self._sessions[session_id] = DataflowSession(
                self._bundle, session_id
            )
        return self._sessions[session_id]

    def get(self, session_id: str) -> DataflowSession | None:
        return self._sessions.get(session_id)

    def _gc(self) -> None:
        now = time.time()
        expired = [
            sid
            for sid, sess in self._sessions.items()
            if now - sess.last_accessed > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
