# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from marimo import _loggers
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._server.api.auth import (
    SESSION_SECRET,
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
    create_proxy_error_handler,
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
    pylsp: int | None
    copilot: int | None


# This must stay in sync with AGENT_CONFIG in
# frontend/src/components/chat/acp/state.ts
ACP_AGENT_PORTS: Final[dict[str, int]] = {
    "claude": 3017,
    "gemini": 3019,
    "codex": 3021,
    "opencode": 3023,
    "cursor": 3025,
}


# Create app
def create_starlette_app(
    *,
    base_url: str,
    host: str | None = None,
    middleware: list[Middleware] | None = None,
    lifespan: Lifespan[Starlette] | None = None,
    enable_auth: bool = True,
    allow_origins: tuple[str, ...] | None = None,
    lsp_servers: list[LspServer] | None = None,
    enable_acp_proxy: bool = False,
    skew_protection: bool = True,
    timeout: float | None = None,
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
                    secret_key=SESSION_SECRET,
                    https_only=GLOBAL_SETTINGS.SESSION_COOKIE_SECURE,
                ),
            ]
        )

    # Do not reflect credentials for wildcard origins.
    allow_credentials = "*" not in allow_origins

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
                allow_credentials=allow_credentials,
                allow_methods=["*"],
                allow_headers=["*"],
                expose_headers=["Content-Disposition"],
            ),
        ]
    )

    if skew_protection:
        final_middlewares.append(Middleware(SkewProtectionMiddleware))

    if lsp_servers is not None:
        final_middlewares.extend(
            _create_lsps_proxy_middleware(
                base_url=base_url, servers=lsp_servers
            )
        )

    if enable_acp_proxy:
        final_middlewares.extend(
            _create_acp_proxy_middleware(base_url=base_url)
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
    base_url: str, *, servers: list[LspServer]
) -> Iterator[Middleware]:
    return (
        Middleware(
            ProxyMiddleware,
            proxy_path=f"{base_url}/lsp/{server.id}",
            target_url=f"http://localhost:{server.port}",
        )
        for server in servers
    )


def _create_acp_proxy_middleware(base_url: str) -> Iterator[Middleware]:
    """Proxy the external ACP agents' websockets through the marimo server.

    The agents listen on fixed localhost ports, which aren't reachable from
    the browser when marimo is served behind a reverse proxy. Proxying them
    under `<base_url>/acp/<agent_id>` keeps the connection same-origin, so it
    only needs the port marimo is already served on.
    """
    return (
        Middleware(
            ProxyMiddleware,
            proxy_path=f"{base_url}/acp/{agent_id}",
            target_url=f"http://127.0.0.1:{port}",
            path_rewrite=_rewrite_acp_path,
            connection_error_handler=create_proxy_error_handler(
                f"The {agent_id} agent is not running. "
                "Start it with the command shown in the agent panel."
            ),
        )
        for agent_id, port in ACP_AGENT_PORTS.items()
    )


def _rewrite_acp_path(_path: str) -> str:
    """ACP agents serve a single endpoint, regardless of the proxied path."""
    return "/message"
