from fastapi import APIRouter

from marimo._server2.api.endpoints.assets import router as assets_router
from marimo._server2.api.endpoints.kernel import router as kernel_router
from marimo._server2.api.endpoints.ws import router as ws_router

# Define the main router
app_router = APIRouter()
app_router.include_router(kernel_router, prefix="/api/kernel", tags=["kernel"])
app_router.include_router(assets_router, tags=["assets"])
app_router.include_router(ws_router, tags=["ws"])
