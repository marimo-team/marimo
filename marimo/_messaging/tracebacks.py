# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

from marimo._runtime.context.types import ContextNotInitializedError


def _highlight_traceback(traceback: str) -> str:
    """
    Highlight the traceback with color.
    """

    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import PythonTracebackLexer

    formatter = HtmlFormatter()

    body = highlight(traceback, PythonTracebackLexer(), formatter)
    return f'<span class="codehilite">{body}</span>'


def write_traceback(traceback: str) -> None:
    from marimo._runtime.context import get_context

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        ctx = None

    if ctx is not None and ctx.stderr is not None:
        sys.stderr.write(_highlight_traceback(traceback))
    else:
        sys.stderr.write(traceback)
