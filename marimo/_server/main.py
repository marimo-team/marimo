# Copyright 2024 Marimo. All rights reserved.
from typing import Any

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from marimo._server.api.lifespans import LIFESPANS
from marimo._server.api.middleware import (
    AuthBackend,
    StripBaseURLMiddleware,
    ValidateServerTokensMiddleware,
)
from marimo._server.api.router import ROUTES
from marimo._server.api.status import HTTPException as MarimoHTTPException


# Convert exceptions to JSON responses
async def handle_error(request: Request, response: Any) -> Any:
    del request
    if isinstance(response, HTTPException):
        return JSONResponse(
            {"detail": response.detail}, status_code=response.status_code
        )
    if isinstance(response, MarimoHTTPException):
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
) -> Starlette:
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(
            StripBaseURLMiddleware,
            base_url=base_url,
        ),
        Middleware(AuthenticationMiddleware, backend=AuthBackend()),
        Middleware(ValidateServerTokensMiddleware),
    ]

    return Starlette(
        routes=ROUTES,
        middleware=middleware,
        lifespan=LIFESPANS,
        exception_handlers={
            Exception: handle_error,
            HTTPException: handle_error,
        },
    )
