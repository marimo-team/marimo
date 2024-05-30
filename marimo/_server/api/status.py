# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from enum import IntEnum
from typing import Optional


class HTTPStatus(IntEnum):
    OK = 200
    BAD_REQUEST = 400
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    UNSUPPORTED_MEDIA_TYPE = 415
    PRECONDITION_REQUIRED = 428
    SERVER_ERROR = 500


class HTTPException(Exception):
    def __init__(
        self,
        status_code: int,
        detail: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail


def is_client_error(status_code: int) -> bool:
    return 400 <= status_code < 500
