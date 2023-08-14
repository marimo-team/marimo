# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from enum import IntEnum


class HTTPStatus(IntEnum):
    OK = 200
    BAD_REQUEST = 400
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    UNSUPPORTED_MEDIA_TYPE = 415
    SERVER_ERROR = 500
