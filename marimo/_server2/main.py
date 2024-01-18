from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from marimo._server2.api.lifespans import LIFESPANS
from marimo._server2.api.router import app_router


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


# Create app
app = FastAPI(
    title="marimo",
    openapi_url="/api/openapi.json",
    lifespan=LIFESPANS,
    generate_unique_id_function=custom_generate_unique_id,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router
app.include_router(app_router)
