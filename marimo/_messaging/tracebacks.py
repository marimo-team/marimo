# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys


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
    from marimo._runtime.runtime import running_in_notebook

    if running_in_notebook():
        sys.stderr.write(_highlight_traceback(traceback))
    else:
        sys.stderr.write(traceback)
