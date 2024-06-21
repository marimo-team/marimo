# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import base64
import secrets
import typing
from typing import TYPE_CHECKING, Any, Dict, Optional

import starlette
import starlette.status as status
from packaging import version
from starlette.datastructures import Secret
from starlette.exceptions import HTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse

from marimo import _loggers

if TYPE_CHECKING:
    from starlette.authentication import AuthenticationError
    from starlette.requests import HTTPConnection
    from starlette.types import ASGIApp, Receive, Scope, Send

from marimo._server.api.deps import AppState

LOGGER = _loggers.marimo_logger()
TOKEN_QUERY_PARAM = "access_token"


# Validates auth
# - Checking for existing session cookie (already authenticated)
# - Or authenticates by access_token in query params
# - Or authenticates by basic auth
def validate_auth(
    conn: HTTPConnection, form_dict: Optional[dict[str, str]] = None
) -> bool:
    LOGGER.debug("Validating auth")
    state = AppState.from_app(conn.app)
    auth_token = str(state.session_manager.auth_token)

    # Check for session cookie
    cookie_session = CookieSession(conn.session)
    # Validate the cookie
    if cookie_session.get_access_token() == auth_token:
        return True  # Success

    # Check for access_token
    if TOKEN_QUERY_PARAM in conn.query_params:
        # Validate the access_token
        if conn.query_params[TOKEN_QUERY_PARAM] == auth_token:
            LOGGER.debug("Validated access_token")
            # Set the cookie
            cookie_session.set_access_token(auth_token)
            return True  # Success

    # Check for form data
    if form_dict is not None:
        # Validate the access_token
        password = form_dict.get("password")
        if password == auth_token:
            LOGGER.debug("Validated access_token")
            # Set the cookie
            cookie_session.set_access_token(auth_token)
            return True
        else:
            return False

    # Check for basic auth
    auth = conn.headers.get("Authorization")
    if auth is not None:
        username, password = _parse_basic_auth_header(auth)
        if username and password == auth_token:
            LOGGER.debug("Validated basic auth")
            # Set the cookie
            cookie_session.set_access_token(auth_token)
            cookie_session.set_username(username)
            return True  # Success

    LOGGER.debug("Invalid auth")
    return False


def _parse_basic_auth_header(
    header: str,
) -> tuple[Optional[str], Optional[str]]:
    scheme, _, credentials = header.partition(" ")

    if scheme.lower() != "basic":
        LOGGER.debug("Invalid auth scheme: %s", scheme)
        return None, None

    decoded = base64.b64decode(credentials).decode("utf-8")
    username, _, password = decoded.partition(":")

    if not password:
        return None, None

    LOGGER.debug("Validated basic auth for user: %s", username)

    return username, password


def raise_basic_auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authorization header required",
        headers={"WWW-Authenticate": "Basic"},
    )


def on_auth_error(
    request: HTTPConnection, error: AuthenticationError
) -> JSONResponse:
    del request
    del error
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Authorization header required"},
        headers={"WWW-Authenticate": "Basic"},
    )


# This is random/new for each server instance
RANDOM_SECRET = Secret(secrets.token_hex(32))


class CookieSession:
    """
    Wrapper around starlette's Session to add typesafety
    """

    def __init__(self, session_state: Dict[str, Any]) -> None:
        self.session_state = session_state

    def get_access_token(self) -> str:
        access_token: str = self.session_state.get("access_token", "")
        return access_token

    def get_username(self) -> str:
        username: str = self.session_state.get("username", "")
        return username

    def set_access_token(self, token: str) -> None:
        self.session_state["access_token"] = token

    def set_username(self, username: str) -> None:
        self.session_state["username"] = username


class CustomSessionMiddleware(SessionMiddleware):
    """
    Wrapper around starlette's SessionMiddleware to:
     - customize the session cookie based on the the port
     - only run in Edit mode
    """

    def __init__(
        self,
        app: ASGIApp,
        secret_key: typing.Union[str, Secret],
        session_cookie: str = "session",
        max_age: typing.Optional[int] = 14
        * 24
        * 60
        * 60,  # 14 days, in seconds
        path: str = "/",
        same_site: typing.Literal["lax", "strict", "none"] = "lax",
        https_only: bool = False,
        domain: typing.Optional[str] = None,
    ) -> None:
        # We can't update the cookie here since
        # we don't have access to the app state

        self.original_session_cookie = session_cookie

        if version.parse(starlette.__version__) >= version.parse("0.32.0"):
            # Domain was added in 0.32.0; we currently don't use it.
            super().__init__(
                app,
                secret_key,
                session_cookie,
                max_age,
                path,
                same_site,
                https_only,
                domain,
            )
        else:
            super().__init__(
                app,
                secret_key,
                session_cookie,
                max_age,
                path,
                same_site,
                https_only,
            )

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        state = AppState.from_app(scope["app"])

        # We key the token cookie by port to avoid conflicts
        # with multiple marimo instances running on the same host
        maybe_port = state.maybe_port
        if maybe_port is not None:
            self.session_cookie = (
                f"{self.original_session_cookie}_{maybe_port}"
            )

        return await super().__call__(scope, receive, send)
