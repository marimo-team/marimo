# Copyright 2023 Marimo. All rights reserved.
"""The marimo library.

marimo is a Python library for making reactive notebooks that double as apps.

marimo is designed to be:

    1. simple
    2. immersive
    3. interactive
    4. seamless
    5. fun
"""

__all__ = [
    "App",
    "accordion",
    "as_html",
    "callout",
    "config",
    "defs",
    "doc",
    "hstack",
    "Html",
    "md",
    "refs",
    "tabs",
    "tree",
    "ui",
    "vstack",
]
__version__ = "0.1.0"

from marimo import config
from marimo._ast.app import App
from marimo._output.doc import doc
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.md import md
from marimo._plugins import ui
from marimo._plugins.stateless.accordion import accordion
from marimo._plugins.stateless.callout_output import callout
from marimo._plugins.stateless.flex import hstack, vstack
from marimo._plugins.stateless.tabs import tabs
from marimo._plugins.stateless.tree import tree
from marimo._runtime.runtime import defs, refs
