# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
from typing import Any, Callable, Optional

import tornado.httputil
import tornado.ioloop
import tornado.web
import tornado.websocket

from marimo import _loggers
from marimo._server.api.status import HTTPStatus
from marimo._server.model import SessionMode
from marimo._server.sessions import Session, get_manager

LOGGER = _loggers.marimo_logger()


def requires_edit(handler: Callable[..., Any]) -> Callable[..., Any]:
    """Mark a function as requiring edit permissions.

    Raises:
    ------
    tornado.web.HTTPError: if session manager is not in edit mode.
    """

    @functools.wraps(handler)
    def _throw_if_not_edit(*args: Any, **kwargs: Any) -> Any:
        if get_manager().mode != SessionMode.EDIT:
            raise tornado.web.HTTPError(HTTPStatus.FORBIDDEN)
        else:
            return handler(*args, **kwargs)

    return _throw_if_not_edit


def server_token_from_header(
    headers: tornado.httputil.HTTPHeaders,
) -> str:
    """Extracts session ID from request header.

    All endpoints require a session ID to be in the request header.
    """
    server_token = headers.get_list("Marimo-Server-Token")
    if not server_token:
        LOGGER.error("Invalid headers (Marimo-Server-Token not found)")
        raise tornado.web.HTTPError(
            HTTPStatus.FORBIDDEN,
            "Invalid headers (Marimo-Server-Token not found)\n\n"
            + str(headers),
        )
    elif len(server_token) > 1:
        LOGGER.error("Invalid headers (> 1 Marimo-Server-Token)")
        raise tornado.web.HTTPError(
            HTTPStatus.FORBIDDEN,
            "Invalid headers (> 1 Marimo-Server-Token)\n\n" + str(headers),
        )
    return server_token[0]


def check_server_token(headers: tornado.httputil.HTTPHeaders) -> None:
    """Throws an HTTPError if no Session is found."""
    server_token = server_token_from_header(headers)
    if server_token != get_manager().server_token:
        LOGGER.error("Mismatched server token: %s", server_token)
        raise tornado.web.HTTPError(
            HTTPStatus.FORBIDDEN, "Invalid server token."
        )


def session_id_from_header(
    headers: tornado.httputil.HTTPHeaders,
) -> str:
    """Extracts session ID from request header.

    All endpoints require a session ID to be in the request header.
    """
    session_id = headers.get_list("Marimo-Session-Id")
    if not session_id:
        raise RuntimeError(
            "Invalid headers (Marimo-Session-Id not found)\n\n" + str(headers)
        )
    elif len(session_id) > 1:
        raise RuntimeError(
            "Invalid headers (> 1 Marimo-Session-Id)\n\n" + str(headers)
        )
    return session_id[0]


def session_from_header(
    headers: tornado.httputil.HTTPHeaders,
) -> Optional[Session]:
    """Get the Session implied by the request header, if any."""
    session_id = session_id_from_header(headers)
    mgr = get_manager()
    session = mgr.get_session(session_id)
    if session is None:
        LOGGER.error("Session with id %s not found", session_id)
    return session


def require_session_from_header(
    headers: tornado.httputil.HTTPHeaders,
) -> Session:
    """Throws an HTTPError if no Session is found."""
    session = session_from_header(headers)
    if session is None:
        raise tornado.web.HTTPError(HTTPStatus.NOT_FOUND, "Session not found.")
    return session
