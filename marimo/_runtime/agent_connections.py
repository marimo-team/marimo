# Copyright 2026 Marimo. All rights reserved.
"""Cell-owned callbacks for the editor's agent connection snapshots."""

from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import msgspec

from marimo import _loggers
from marimo._messaging.agents import (
    AgentError,
    AgentInfo,
    ConnectionSubscriptionRequest,
    connection_namespace,
)
from marimo._messaging.context import EXECUTION_CTX
from marimo._runtime.agent_messaging import call
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._runtime.functions import Function
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._messaging.agents import AgentConnection
    from marimo._runtime.context.types import RuntimeContext

LOGGER = _loggers.marimo_logger()


@dataclass
class _ConnectionUpdate:
    revision: int
    agents: list[dict[str, Any]]


class ConnectionSubscription(CellLifecycleItem):
    def __init__(
        self,
        config: AgentConnection,
        callback: Callable[[tuple[AgentInfo, ...]], None],
    ) -> None:
        self._config = config
        self._callback: Callable[[tuple[AgentInfo, ...]], None] | None = (
            callback
        )
        self._id = uuid4().hex
        self._namespace = connection_namespace(self._id)
        self._context: RuntimeContext | None = None
        self._active = True
        self._revision = 0
        self._snapshot: tuple[AgentInfo, ...] | None = None
        self._lock = threading.RLock()

    def create(self, context: RuntimeContext) -> None:
        self._context = context
        function = Function("update", _ConnectionUpdate, self._update)
        execution = EXECUTION_CTX.get()
        function.cell_id = (
            CellId_t(execution.cell_id)
            if execution is not None
            else context.cell_id
        )
        context.function_registry.register(self._namespace, function)
        try:
            call(
                self._config,
                "connections",
                timeout=30,
                subscription=ConnectionSubscriptionRequest(self._id),
            )
        except BaseException:
            self.close()
            raise

    def _update(self, update: _ConnectionUpdate) -> None:
        snapshot = msgspec.convert(update.agents, type=tuple[AgentInfo, ...])
        with self._lock:
            if not self._active or update.revision <= self._revision:
                return
            self._revision = update.revision
            if snapshot == self._snapshot:
                return
            self._snapshot = snapshot
            callback = self._callback
            assert callback is not None
            result = callback(snapshot)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError(
                    "Agent connection callbacks must be synchronous"
                )

    def close(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._active = False
            self._callback = None
            context, self._context = self._context, None
        if context is not None:
            context.function_registry.delete(self._namespace)
        try:
            call(
                self._config,
                "connections",
                timeout=1,
                subscription=ConnectionSubscriptionRequest(
                    self._id, active=False
                ),
            )
        except AgentError:
            # Local removal also makes queued updates unable to call the user.
            LOGGER.debug("Could not release agent observer", exc_info=True)

    def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
        del context, deletion
        self.close()
        return True
