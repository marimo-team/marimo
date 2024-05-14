# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import secrets


# Adapted from starlette, to avoid a dependency when running without starlette.
class AuthToken:
    """
    Holds a string value that should not be revealed in tracebacks etc.
    You should cast the value to `str` at the point it is required.
    """

    def __init__(self, value: str):
        self._value = value

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        return f"{class_name}('**********')"

    def __str__(self) -> str:
        return self._value

    def __bool__(self) -> bool:
        return bool(self._value)

    @staticmethod
    def random() -> AuthToken:
        return AuthToken(secrets.token_urlsafe(16))

    @staticmethod
    def from_code(code: str) -> AuthToken:
        return AuthToken(str(hash(code)))

    @staticmethod
    def is_empty(token: AuthToken) -> bool:
        return str(token) == ""


class SkewProtectionToken:
    """
    Provides a token that is sent to the client on the first request and
    is used to protect against version skew bugs.

    This can happen when new code is deployed to the server but the client
    still has only application loaded.
    """

    def __init__(self, token: str) -> None:
        self.token = token

    @staticmethod
    def from_code(code: str) -> SkewProtectionToken:
        return SkewProtectionToken(str(hash(code)))

    @staticmethod
    def random() -> SkewProtectionToken:
        return SkewProtectionToken(secrets.token_urlsafe(16))

    def __str__(self) -> str:
        return self.token
