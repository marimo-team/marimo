# Copyright 2026 Marimo. All rights reserved.
"""Internal API for rendering marimo notebooks as HTML."""

from marimo._server.templates.api import (
    render_notebook,
    render_static_notebook,
)

__all__ = [
    "render_notebook",
    "render_static_notebook",
]
