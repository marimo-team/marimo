# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import hmac
import secrets
import typing
from typing import TYPE_CHECKING, Any

import starlette
from starlette import status
from starlette.datastructures import Secret
from starlette.exceptions import HTTPException
from starlette.middleware.authentication import AuthenticationMiddleware
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
    conn: HTTPConnection, form_dict: dict[str, str] | None = None
) -> bool:
    state = AppState.from_app(conn.app)
    auth_token = str(state.session_manager.auth_token)

    # Check for session cookie
    cookie_session = CookieSession(conn.session)

    # Validate the cookie
    if hmac.compare_digest(cookie_session.get_access_token(), auth_token):
        return True  # Success

    # Check for access_token
    if TOKEN_QUERY_PARAM in conn.query_params:
        # Validate the access_token
        if hmac.compare_digest(
            conn.query_params[TOKEN_QUERY_PARAM], auth_token
        ):
            LOGGER.debug("Validated access_token from query param")
            # Set the cookie
            cookie_session.set_access_token(auth_token)
            return True  # Success

    # Check for form data
    if form_dict is not None:
        # Validate the access_token
        password = form_dict.get("password")
        if password and hmac.compare_digest(password, auth_token):
            LOGGER.debug("Validated access_token from form data")
            # Set the cookie
            cookie_session.set_access_token(auth_token)
            return True
        else:
            LOGGER.warning("Invalid password from form data.")
            return False

    # Check for Authorization header (Bearer or Basic)
    auth = conn.headers.get("Authorization")
    if auth is not None:
        scheme, _, credentials = auth.partition(" ")
        scheme_lower = scheme.lower()

        if scheme_lower == "bearer" and hmac.compare_digest(
            credentials, auth_token
        ):
            LOGGER.debug("Validated bearer token from header")
            cookie_session.set_access_token(auth_token)
            return True  # Success

        if scheme_lower == "basic":
            username, password = _parse_basic_auth_credentials(credentials)
            if (
                username
                and password
                and hmac.compare_digest(password, auth_token)
            ):
                LOGGER.debug("Validated basic auth from header")
                cookie_session.set_access_token(auth_token)
                cookie_session.set_username(username)
                return True  # Success

    LOGGER.debug("Invalid auth")
    return False


def _parse_basic_auth_credentials(
    credentials: str,
) -> tuple[str | None, str | None]:
    try:
        decoded = base64.b64decode(credentials).decode("utf-8")
    except Exception:
        LOGGER.debug("Invalid base64 in basic auth credentials")
        return None, None

    username, _, password = decoded.partition(":")

    if not password:
        return None, None

    LOGGER.debug("Parsed basic auth credentials for user: %s", username)

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

    def __init__(self, session_state: dict[str, Any]) -> None:
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
     - customize the session cookie based on the port and base URL
     - only run in Edit mode
    """

    def __init__(
        self,
        app: ASGIApp,
        secret_key: str | Secret,
        session_cookie: str = "session",
        max_age: int | None = 14 * 24 * 60 * 60,  # 14 days, in seconds
        path: str = "/",
        same_site: typing.Literal["lax", "strict", "none"] = "lax",
        https_only: bool = False,
        domain: str | None = None,
    ) -> None:
        from packaging import version

        # We can't update the cookie here since
        # we don't have access to the app state

        self.original_session_cookie = session_cookie
        self.original_path = path

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
        cookie_name = self.original_session_cookie
        maybe_port = state.maybe_port
        if maybe_port is not None:
            cookie_name = f"{cookie_name}_{maybe_port}"

        base_url = getattr(state.state, "base_url", "")
        if base_url:
            slug = base_url.lstrip("/").replace("/", "_")
            if slug:
                cookie_name = f"{cookie_name}_{slug}"
            self.path = base_url
        else:
            self.path = self.original_path

        self.session_cookie = cookie_name

        return await super().__call__(scope, receive, send)


# Wrapper around starlette's AuthenticationMiddleware to
# restore the 'user' key in the request object if one was
# set by prior middleware
class CustomAuthenticationMiddleware(AuthenticationMiddleware):
    KEY = "_marimo_prev_user"

    def __init__(self, app: ASGIApp, *args: Any, **kwargs: Any) -> None:
        # The AuthenticationMiddleware sets the 'user' key in the scope, but
        # we want to keep the developer-defined user in the scope so that
        async def wrapped_app(
            scope: Scope, receive: Receive, send: Send
        ) -> None:
            # Get the developer-defined that we saved earlier
            developer_defined_user = scope.get(self.KEY)
            # Store it back in the scope
            if developer_defined_user is not None:
                scope["user"] = developer_defined_user
            await app(scope, receive, send)

        super().__init__(wrapped_app, *args, **kwargs)

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        # If a developer has defined a user, store it in scope
        # so that the wrapped app can access it
        developer_defined_user = scope.get("user")
        scope[self.KEY] = developer_defined_user
        await super().__call__(scope, receive, send)
        # Delete the key from scope
        del scope[self.KEY]
