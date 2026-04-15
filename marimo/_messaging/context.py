# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass

from marimo._runtime.commands import HTTPRequest

RunId_t = str
RUN_ID_CTX = ContextVar[RunId_t | None]("run_id")

HTTP_REQUEST_CTX = ContextVar[HTTPRequest | None]("http_request")


@dataclass
class run_id_context:
    """Context manager for setting and unsetting the run ID."""

    run_id: RunId_t

    def __init__(self) -> None:
        self.run_id = str(uuid.uuid4())

    def __enter__(self) -> None:
        self.token = RUN_ID_CTX.set(self.run_id)

    def __exit__(self, *_: object) -> None:
        RUN_ID_CTX.reset(self.token)


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
    path: str = request.url.get("path", "")
    return path.endswith("/api/kernel/execute")
