# Copyright 2024 Marimo. All rights reserved.
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Route, Mount, WebsSocketRoute
from starlette.middleware.cors import CORSMiddleware

from marimo._server2.api.lifespans import LIFESPANS
from marimo._server2.api.router import ROUTES


# def custom_generate_unique_id(route: APIRoute) -> str:
#    return f"{route.tags[0]}-{route.name}"


# CORS
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
]


app = Starlette(
    routes=ROUTES,
    middleware=middleware,
    lifespan=LIFESPANS,
)
# Create app
# app = FastAPI(
#    title="marimo",
#    openapi_url="/api/openapi.json",
#    lifespan=LIFESPANS,
#    generate_unique_id_function=custom_generate_unique_id,
# )
# Router
# app.include_router(app_router)
