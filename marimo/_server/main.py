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
from marimo._server.api.auth import (
    RANDOM_SECRET,
    CustomSessionMiddleware,
    on_auth_error,
)
from marimo._server.api.middleware import (
    AuthBackend,
    OpenTelemetryMiddleware,
    ProxyMiddleware,
    SkewProtectionMiddleware,
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
    if isinstance(response, NotImplementedError):
        return JSONResponse({"detail": "Not supported"}, status_code=501)
    if isinstance(response, TypeError):
        return JSONResponse({"detail": str(response)}, status_code=500)
    if isinstance(response, Exception):
        return JSONResponse({"detail": str(response)}, status_code=500)
    return response


# Create app
def create_starlette_app(
    *,
    base_url: str,
    host: Optional[str] = None,
    middleware: Optional[List[Middleware]] = None,
    lifespan: Optional[Lifespan[Starlette]] = None,
    enable_auth: bool = True,
    allow_origins: Optional[tuple[str, ...]] = None,
    lsp_port: Optional[int] = None,
) -> Starlette:
    final_middlewares: List[Middleware] = []

    if allow_origins is None:
        allow_origins = ("localhost", "127.0.0.1") + (
            (host,) if host is not None else ()
        )

    if enable_auth:
        final_middlewares.extend(
            [
                Middleware(
                    CustomSessionMiddleware,
                    secret_key=RANDOM_SECRET,
                ),
            ]
        )

    final_middlewares.extend(
        [
            Middleware(OpenTelemetryMiddleware),
            Middleware(
                AuthenticationMiddleware,
                backend=AuthBackend(should_authenticate=enable_auth),
                on_error=on_auth_error,
            ),
            Middleware(
                CORSMiddleware,
                allow_origins=allow_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
            Middleware(SkewProtectionMiddleware),
            _create_mpl_proxy_middleware(),
        ]
    )

    if lsp_port is not None:
        final_middlewares.append(_create_lsp_proxy_middleware(lsp_port))

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


def _create_mpl_proxy_middleware() -> Middleware:
    # MPL proxy logic
    def mpl_target_url(path: str) -> str:
        # Path format: /mpl/<port>/rest/of/path
        port = path.split("/", 3)[2]
        return f"http://localhost:{port}"

    def mpl_path_rewrite(path: str) -> str:
        # Remove the /mpl/<port>/ prefix
        rest = path.split("/", 3)[3]
        return f"/{rest}"

    return Middleware(
        ProxyMiddleware,
        proxy_path="/mpl",
        target_url=mpl_target_url,
        path_rewrite=mpl_path_rewrite,
    )


def _create_lsp_proxy_middleware(lsp_port: int) -> Middleware:
    return Middleware(
        ProxyMiddleware,
        proxy_path="/lsp",
        target_url=f"http://localhost:{lsp_port}",
        # Remove the /lsp prefix
        path_rewrite=lambda path: path.replace("/lsp", ""),
    )
