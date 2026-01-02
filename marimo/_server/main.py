# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from marimo import _loggers
from marimo._server.api.auth import (
    RANDOM_SECRET,
    CustomAuthenticationMiddleware,
    CustomSessionMiddleware,
    on_auth_error,
)
from marimo._server.api.middleware import (
    AuthBackend,
    OpenTelemetryMiddleware,
    ProxyMiddleware,
    SkewProtectionMiddleware,
    TimeoutMiddleware,
)
from marimo._server.api.router import build_routes
from marimo._server.errors import handle_error
from marimo._server.lsp import LspServer
from marimo._server.registry import MIDDLEWARE_REGISTRY
from marimo._utils.http import (
    HTTPException as MarimoHTTPException,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.types import Lifespan

LOGGER = _loggers.marimo_logger()


@dataclass
class LspPorts:
    pylsp: Optional[int]
    copilot: Optional[int]


# Create app
def create_starlette_app(
    *,
    base_url: str,
    host: Optional[str] = None,
    middleware: Optional[list[Middleware]] = None,
    lifespan: Optional[Lifespan[Starlette]] = None,
    enable_auth: bool = True,
    allow_origins: Optional[tuple[str, ...]] = None,
    lsp_servers: Optional[list[LspServer]] = None,
    skew_protection: bool = True,
    timeout: Optional[float] = None,
) -> Starlette:
    final_middlewares: list[Middleware] = []

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
                CustomAuthenticationMiddleware,
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
        ]
    )

    if skew_protection:
        final_middlewares.append(Middleware(SkewProtectionMiddleware))

    if lsp_servers is not None:
        final_middlewares.extend(
            _create_lsps_proxy_middleware(servers=lsp_servers)
        )

    if middleware:
        final_middlewares.extend(middleware)

    final_middlewares.extend(MIDDLEWARE_REGISTRY.get_all())

    app = Starlette(
        routes=build_routes(base_url=base_url),
        middleware=final_middlewares,
        lifespan=lifespan,
        exception_handlers={
            Exception: handle_error,
            HTTPException: handle_error,
            MarimoHTTPException: handle_error,
            ModuleNotFoundError: handle_error,
        },
    )
    if timeout is not None:
        app.add_middleware(
            TimeoutMiddleware,
            app_state=app.state,
            timeout_duration_minutes=timeout,
        )
    return app


def _create_lsps_proxy_middleware(
    *, servers: list[LspServer]
) -> Iterator[Middleware]:
    return (
        Middleware(
            ProxyMiddleware,
            proxy_path=f"/lsp/{server.id}",
            target_url=f"http://localhost:{server.port}",
        )
        for server in servers
    )
