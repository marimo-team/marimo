# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, List

from marimo._server.api.endpoints.ai import router as ai_router
from marimo._server.api.endpoints.assets import router as assets_router
from marimo._server.api.endpoints.config import router as config_router
from marimo._server.api.endpoints.datasources import (
    router as datasources_router,
)
from marimo._server.api.endpoints.documentation import (
    router as documentation_router,
)
from marimo._server.api.endpoints.editing import router as editing_router
from marimo._server.api.endpoints.execution import router as execution_router
from marimo._server.api.endpoints.export import router as export_router
from marimo._server.api.endpoints.file_explorer import (
    router as file_explorer_router,
)
from marimo._server.api.endpoints.files import router as files_router
from marimo._server.api.endpoints.health import router as health_router
from marimo._server.api.endpoints.home import router as home_router
from marimo._server.api.endpoints.login import router as login_router
from marimo._server.api.endpoints.terminal import router as terminal_router
from marimo._server.api.endpoints.ws import router as ws_router
from marimo._server.router import APIRouter

if TYPE_CHECKING:
    from starlette.routing import BaseRoute


# Define the app routes
def build_routes(base_url: str = "") -> List[BaseRoute]:
    app_router = APIRouter(prefix=base_url)
    app_router.include_router(
        execution_router, prefix="/api/kernel", name="execution"
    )
    app_router.include_router(
        config_router, prefix="/api/kernel", name="config"
    )
    app_router.include_router(
        editing_router, prefix="/api/kernel", name="editing"
    )
    app_router.include_router(files_router, prefix="/api/kernel", name="files")
    app_router.include_router(
        file_explorer_router, prefix="/api/files", name="file_explorer"
    )
    app_router.include_router(
        documentation_router, prefix="/api/documentation", name="documentation"
    )
    app_router.include_router(
        datasources_router, prefix="/api/datasources", name="datasources"
    )
    app_router.include_router(ai_router, prefix="/api/ai", name="ai")
    app_router.include_router(home_router, prefix="/api/home", name="home")
    app_router.include_router(login_router, prefix="/auth", name="auth")
    app_router.include_router(
        export_router, prefix="/api/export", name="export"
    )
    app_router.include_router(
        terminal_router, prefix="/terminal", name="terminal"
    )
    app_router.include_router(health_router, name="health")
    app_router.include_router(ws_router, name="ws")
    app_router.include_router(assets_router, name="assets")

    return app_router.routes
