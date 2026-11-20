# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from marimo._runtime.commands import HTTPRequest

if TYPE_CHECKING:
    from marimo._runtime.execution import ExecutionAttempt

RunId_t = str
RUN_ID_CTX = ContextVar[RunId_t | None]("run_id")


@dataclass(frozen=True)
class ExecutionTag:
    """The evaluation producing a cell's notifications."""

    id: str
    cell_id: str
    run_id: str | None = None
    attempt: ExecutionAttempt | None = field(
        default=None, compare=False, repr=False
    )


EXECUTION_CTX = ContextVar[ExecutionTag | None]("execution", default=None)


def execution_id_for(cell_id: str) -> str | None:
    execution = EXECUTION_CTX.get()
    return execution.id if execution and execution.cell_id == cell_id else None


HTTP_REQUEST_CTX = ContextVar[HTTPRequest | None]("http_request")


@dataclass
class run_id_context:
    """Context manager for setting and unsetting the run ID."""

    run_id: RunId_t

    def __init__(self, run_id: RunId_t | None = None) -> None:
        self.run_id = run_id if run_id is not None else str(uuid.uuid4())

    def __enter__(self) -> None:
        self.token = RUN_ID_CTX.set(self.run_id)

    def __exit__(self, *_: object) -> None:
        RUN_ID_CTX.reset(self.token)


@dataclass
class execution_id_context:
    """Identify one evaluation, including its buffered and background output."""

    cell_id: str
    id: str | None = None
    attempt: ExecutionAttempt | None = None

    def __enter__(self) -> None:
        self.token = EXECUTION_CTX.set(
            ExecutionTag(
                self.id or str(uuid.uuid4()),
                self.cell_id,
                RUN_ID_CTX.get(None),
                self.attempt,
            )
        )

    def __exit__(self, *_: object) -> None:
        EXECUTION_CTX.reset(self.token)


@dataclass
class http_request_context:
    """Context manager for setting and unsetting the HTTP request."""

    request: HTTPRequest | None

    def __init__(self, request: HTTPRequest | None) -> None:
        self.request = request

    def __enter__(self) -> None:
        self.token = HTTP_REQUEST_CTX.set(self.request)

    def __exit__(self, *_: object) -> None:
        HTTP_REQUEST_CTX.reset(self.token)


def is_code_mode_request() -> bool:
    """True when the current request originated from the /api/kernel/execute endpoint."""
    request = HTTP_REQUEST_CTX.get(None)
    if request is None:
        return False
    path = cast("str", request.url.get("path", ""))
    return path.endswith("/api/kernel/execute")
