# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._messaging.ops import MissingPackageAlert
from marimo._runtime.packages.utils import is_python_isolated
from marimo._server.api.deps import AppState
from marimo._server.api.status import (
    HTTPException as MarimoHTTPException,
    is_client_error,
)
from marimo._server.ids import ConsumerId
from marimo._server.model import SessionMode
from marimo._server.sessions import send_message_to_consumer

if TYPE_CHECKING:
    from starlette.requests import Request

LOGGER = _loggers.marimo_logger()


# Convert exceptions to JSON responses
# In the case of a ModuleNotFoundError, we try to send a MissingPackageAlert to the client
# to install the missing package
async def handle_error(request: Request, response: Any) -> Any:
    if isinstance(response, HTTPException):
        # Turn 403s into 401s to collect auth
        if response.status_code == 403:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header required"},
                headers={"WWW-Authenticate": "Basic"},
            )
        return JSONResponse(
            {"detail": response.detail},
            status_code=response.status_code,
            headers=response.headers,
        )
    if isinstance(response, MarimoHTTPException):
        # Log server errors
        if not is_client_error(response.status_code):
            LOGGER.exception(response)
        return JSONResponse(
            {"detail": response.detail},
            status_code=response.status_code,
        )
    if isinstance(response, ModuleNotFoundError) and response.name:
        try:
            app_state = AppState(request)
            session_id = app_state.get_current_session_id()
            session = app_state.get_current_session()
            # If we're in an edit session, send an package installation request
            if (
                session_id is not None
                and session is not None
                and app_state.mode == SessionMode.EDIT
            ):
                send_message_to_consumer(
                    session=session,
                    operation=MissingPackageAlert(
                        packages=[response.name],
                        isolated=is_python_isolated(),
                    ),
                    consumer_id=ConsumerId(session_id),
                )
            return JSONResponse({"detail": str(response)}, status_code=500)
        except Exception as e:
            LOGGER.warning(f"Failed to send missing package alert: {e}")
    if isinstance(response, NotImplementedError):
        return JSONResponse({"detail": "Not supported"}, status_code=501)
    if isinstance(response, TypeError):
        return JSONResponse({"detail": str(response)}, status_code=500)
    if isinstance(response, Exception):
        return JSONResponse({"detail": str(response)}, status_code=500)
    return response
