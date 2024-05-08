# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from marimo import _loggers
from marimo._server.api.middleware import (
    AuthBackend,
    ValidateServerTokensMiddleware,
)
from marimo._server.api.router import build_routes
from marimo._server.api.status import (
    HTTPException as MarimoHTTPException,
    is_client_error,
)

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import Lifespan

LOGGER = _loggers.marimo_logger()


# Convert exceptions to JSON responses
async def handle_error(request: Request, response: Any) -> Any:
    del request
    if isinstance(response, HTTPException):
        return JSONResponse(
            {"detail": response.detail}, status_code=response.status_code
        )
    if isinstance(response, MarimoHTTPException):
        # Log server errors
        if not is_client_error(response.status_code):
            LOGGER.exception(response)
        return JSONResponse(
            {"detail": response.detail}, status_code=response.status_code
        )
    if isinstance(response, TypeError):
        return JSONResponse({"detail": str(response)}, status_code=500)
    if isinstance(response, Exception):
        return JSONResponse({"detail": str(response)}, status_code=500)
    return response


# Create app
def create_starlette_app(
    base_url: str,
    middleware: Optional[List[Middleware]] = None,
    lifespan: Optional[Lifespan[Starlette]] = None,
) -> Starlette:
    final_middlewares: List[Middleware] = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(AuthenticationMiddleware, backend=AuthBackend()),
        Middleware(ValidateServerTokensMiddleware),
    ]

    if middleware:
        final_middlewares.extend(middleware)

    return Starlette(
        routes=build_routes(base_url=base_url),
        middleware=final_middlewares,
        lifespan=lifespan,
        exception_handlers={
            Exception: handle_error,
            HTTPException: handle_error,
            MarimoHTTPException: handle_error,
        },
    )
