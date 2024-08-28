# Copyright 2024 Marimo. All rights reserved.
"""The marimo library.

The marimo library brings marimo notebooks to life with powerful
UI elements to interact with and transform data, dynamic markdown,
and more.

marimo is designed to be:

    1. simple
    2. immersive
    3. interactive
    4. seamless
    5. fun
"""

from __future__ import annotations

__all__ = [
    "App",
    "Cell",
    "MarimoStopError",
    "create_asgi_app",
    "MarimoIslandGenerator",
    "accordion",
    "carousel",
    "as_html",
    "audio",
    "callout",
    "capture_stdout",
    "capture_stderr",
    "center",
    "cli_args",
    "defs",
    "doc",
    "download",
    "hstack",
    "Html",
    "icon",
    "image",
    "lazy",
    "left",
    "md",
    "mermaid",
    "mpl",
    "nav_menu",
    "output",
    "plain",
    "plain_text",
    "pdf",
    "query_params",
    "redirect_stderr",
    "redirect_stdout",
    "refs",
    "right",
    "running_in_notebook",
    "routes",
    "sidebar",
    "stat",
    "state",
    "status",
    "stop",
    "sql",
    "style",
    "tabs",
    "tree",
    "ui",
    "video",
    "vstack",
]
__version__ = "0.8.4"

from marimo._ast.app import App
from marimo._ast.cell import Cell
from marimo._islands.island_generator import MarimoIslandGenerator
from marimo._output.doc import doc
from marimo._output.formatting import as_html, plain
from marimo._output.hypertext import Html
from marimo._output.justify import center, left, right
from marimo._output.md import md
from marimo._plugins import ui
from marimo._plugins.stateless import mpl, status
from marimo._plugins.stateless.accordion import accordion
from marimo._plugins.stateless.audio import audio
from marimo._plugins.stateless.callout import callout
from marimo._plugins.stateless.carousel import carousel
from marimo._plugins.stateless.download import download
from marimo._plugins.stateless.flex import hstack, vstack
from marimo._plugins.stateless.icon import icon
from marimo._plugins.stateless.image import image
from marimo._plugins.stateless.lazy import lazy
from marimo._plugins.stateless.mermaid import mermaid
from marimo._plugins.stateless.nav_menu import nav_menu
from marimo._plugins.stateless.pdf import pdf
from marimo._plugins.stateless.plain_text import plain_text
from marimo._plugins.stateless.routes import routes
from marimo._plugins.stateless.sidebar import sidebar
from marimo._plugins.stateless.stat import stat
from marimo._plugins.stateless.style import style
from marimo._plugins.stateless.tabs import tabs
from marimo._plugins.stateless.tree import tree
from marimo._plugins.stateless.video import video
from marimo._runtime import output
from marimo._runtime.capture import (
    capture_stderr,
    capture_stdout,
    redirect_stderr,
    redirect_stdout,
)
from marimo._runtime.context.utils import running_in_notebook
from marimo._runtime.control_flow import MarimoStopError, stop
from marimo._runtime.runtime import cli_args, defs, query_params, refs
from marimo._runtime.state import state
from marimo._server.asgi import create_asgi_app
from marimo._sql.sql import sql
