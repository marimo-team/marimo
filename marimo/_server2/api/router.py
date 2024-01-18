# Copyright 2024 Marimo. All rights reserved.
from fastapi import APIRouter

from marimo._server2.api.endpoints.assets import router as assets_router
from marimo._server2.api.endpoints.config import router as config_router
from marimo._server2.api.endpoints.editing import router as editing_router
from marimo._server2.api.endpoints.execution import router as execution_router
from marimo._server2.api.endpoints.files import router as files_router
from marimo._server2.api.endpoints.ws import router as ws_router

# Define the main router
app_router = APIRouter()
app_router.include_router(
    execution_router, prefix="/api/kernel", tags=["kernel"]
)
app_router.include_router(config_router, prefix="/api/kernel", tags=["config"])
app_router.include_router(
    editing_router, prefix="/api/kernel", tags=["editing"]
)
app_router.include_router(files_router, prefix="/api/kernel", tags=["files"])
app_router.include_router(assets_router, tags=["assets"])

app_router.include_router(ws_router, tags=["ws"])
