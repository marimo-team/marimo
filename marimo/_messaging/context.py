# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Optional

from marimo._runtime.requests import HTTPRequest

RunId_t = str
RUN_ID_CTX = ContextVar[Optional[RunId_t]]("run_id")

HTTP_REQUEST_CTX = ContextVar[Optional[HTTPRequest]]("http_request")


@dataclass
class run_id_context:
    """Context manager for setting and unsetting the run ID."""

    run_id: RunId_t

    def __init__(self) -> None:
        self.run_id = str(uuid.uuid4())

    def __enter__(self) -> None:
        self.token = RUN_ID_CTX.set(self.run_id)

    def __exit__(self, *_: Any) -> None:
        RUN_ID_CTX.reset(self.token)


@dataclass
class http_request_context:
    """Context manager for setting and unsetting the HTTP request."""

    request: Optional[HTTPRequest]

    def __init__(self, request: Optional[HTTPRequest]) -> None:
        self.request = request

    def __enter__(self) -> None:
        self.token = HTTP_REQUEST_CTX.set(self.request)

    def __exit__(self, *_: Any) -> None:
        HTTP_REQUEST_CTX.reset(self.token)
