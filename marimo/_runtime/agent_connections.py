# Copyright 2026 Marimo. All rights reserved.
"""Callbacks for changes to agent connections."""

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
from marimo._runtime.agent_messaging import call
from marimo._runtime.functions import Function

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._messaging.agents import AgentConnection
    from marimo._runtime.functions import FunctionRegistry

LOGGER = _loggers.marimo_logger()


@dataclass
class _ConnectionUpdate:
    agents: list[dict[str, Any]]


class ConnectionSubscription:
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
        self._registry: FunctionRegistry | None = None
        self._registered = False
        self._lock = threading.RLock()

    def create(self, registry: FunctionRegistry) -> None:
        self._registry = registry
        function = Function(
            "update", _ConnectionUpdate, self._update, cell_bound=False
        )
        registry.register(self._namespace, function)
        try:
            call(
                self._config,
                "connections",
                timeout=1,
                subscription=ConnectionSubscriptionRequest(self._id),
            )
            self._registered = True
        except BaseException:
            self.close()
            raise

    def _update(self, update: _ConnectionUpdate) -> None:
        snapshot = msgspec.convert(update.agents, type=tuple[AgentInfo, ...])
        with self._lock:
            callback = self._callback
            if callback is None:
                return
            result = callback(snapshot)
            if inspect.isawaitable(result):
                if inspect.iscoroutine(result):
                    result.close()
                raise TypeError(
                    "Agent connection callbacks must be synchronous"
                )

    def close(self) -> None:
        with self._lock:
            if self._callback is None:
                return
            self._callback = None
            registry, self._registry = self._registry, None
        if registry is not None:
            registry.delete(self._namespace)
        if not self._registered:
            return
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
