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
    # Core API
    "App",
    "Cell",
    "create_asgi_app",
    "MarimoIslandGenerator",
    "MarimoStopError",
    # Other namespaces
    "ai",
    "ui",
    # Application elements
    "accordion",
    "app_meta",
    "as_html",
    "audio",
    "cache",
    "callout",
    "capture_stderr",
    "capture_stdout",
    "carousel",
    "center",
    "cli_args",
    "defs",
    "doc",
    "download",
    "hstack",
    "Html",
    "icon",
    "iframe",
    "image",
    "lazy",
    "left",
    "lru_cache",
    "md",
    "mermaid",
    "mpl",
    "nav_menu",
    "notebook_dir",
    "output",
    "pdf",
    "persistent_cache",
    "plain",
    "plain_text",
    "query_params",
    "redirect_stderr",
    "redirect_stdout",
    "refs",
    "right",
    "routes",
    "running_in_notebook",
    "show_code",
    "sidebar",
    "sql",
    "stat",
    "state",
    "status",
    "stop",
    "style",
    "tabs",
    "tree",
    "video",
    "vstack",
]
__version__ = "0.9.1"

from marimo._ast.app import App
from marimo._ast.cell import Cell
from marimo._islands.island_generator import MarimoIslandGenerator
from marimo._output.doc import doc
from marimo._output.formatting import as_html, iframe, plain
from marimo._output.hypertext import Html
from marimo._output.justify import center, left, right
from marimo._output.md import md
from marimo._output.show_code import show_code
from marimo._plugins import ai, ui
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
from marimo._runtime.runtime import (
    app_meta,
    cli_args,
    defs,
    notebook_dir,
    query_params,
    refs,
)
from marimo._runtime.state import state
from marimo._save.save import cache, lru_cache, persistent_cache
from marimo._server.asgi import create_asgi_app
from marimo._sql.sql import sql
