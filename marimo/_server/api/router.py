# Copyright 2024 Marimo. All rights reserved.


from marimo._server.api.endpoints.assets import router as assets_router
from marimo._server.api.endpoints.config import router as config_router
from marimo._server.api.endpoints.editing import router as editing_router
from marimo._server.api.endpoints.execution import router as execution_router
from marimo._server.api.endpoints.files import router as files_router
from marimo._server.api.endpoints.ws import router as ws_router
from marimo._server.router import APIRouter

# Define the main router
app_router = APIRouter()
app_router.include_router(
    execution_router, prefix="/api/kernel", name="execution"
)
app_router.include_router(config_router, prefix="/api/kernel", name="config")
app_router.include_router(editing_router, prefix="/api/kernel", name="editing")
app_router.include_router(files_router, prefix="/api/kernel", name="files")
app_router.include_router(assets_router)
app_router.include_router(ws_router)

ROUTES = app_router.routes
