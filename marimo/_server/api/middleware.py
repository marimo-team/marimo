# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
    SimpleUser,
)
from starlette.requests import HTTPConnection

from marimo._server.model import SessionMode


class AuthBackend(AuthenticationBackend):
    async def authenticate(
        self, conn: HTTPConnection
    ) -> Optional[tuple["AuthCredentials", "BaseUser"]]:
        mode = conn.app.state.session_manager.mode
        if mode is None:
            return None
        if mode == SessionMode.RUN:
            return AuthCredentials(["read"]), SimpleUser("user")
        elif mode == SessionMode.EDIT:
            return AuthCredentials(["read", "edit"]), SimpleUser("user")
        return None
