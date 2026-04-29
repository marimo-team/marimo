#!/usr/bin/env python3
"""Standalone dataflow API server for the demo notebook.

Usage:
    uv run python serve.py

This starts an HTTP server on port 2719 exposing:
  GET  /api/v1/dataflow/schema
  POST /api/v1/dataflow/run

The React frontend (in ./frontend/) should proxy /api to this server.
"""

from __future__ import annotations

import uvicorn
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

# Import the demo notebook app
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from notebook import app  # noqa: E402

from marimo._ast.app import InternalApp  # noqa: E402
from marimo._dataflow.session import DataflowSessionManager  # noqa: E402
from marimo._server.api.endpoints.dataflow import (  # noqa: E402
    register_dataflow_app,
    router,
)


def create_app() -> Starlette:
    internal = InternalApp(app)
    register_dataflow_app("__default__", DataflowSessionManager(internal))

    application = Starlette(
        routes=[Mount("/api/v1/dataflow", routes=router.routes)],
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return application


_app = create_app()

if __name__ == "__main__":
    print("Starting dataflow API server on http://localhost:2719")
    print("  GET  /api/v1/dataflow/schema")
    print("  POST /api/v1/dataflow/run")
    print()
    uvicorn.run(_app, host="0.0.0.0", port=2719)
