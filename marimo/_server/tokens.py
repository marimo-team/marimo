# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import secrets

from starlette.datastructures import Secret


class AuthToken(Secret):
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
