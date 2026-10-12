# Copyright 2026 Marimo. All rights reserved.
"""Host API routes and session integration for `marimo edit`."""

HOST_API_PATH = "/api/marimo/v1"
"""Host API path relative to the server's base URL."""

OPERATIONS = [
    "notebook.create",
    "notebook.update",
    "notebook.delete",
    "notebook.open",
    "notebook.edit",
    "runtime.start",
    "runtime.stop",
    "runtime.restart",
    "runtime.run",
]
"""Supported operations advertised in the `host` object."""
