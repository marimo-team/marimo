# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

from marimo._messaging.types import Stderr


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
    if isinstance(sys.stderr, Stderr):
        sys.stderr._write_with_mimetype(
            _highlight_traceback(traceback),
            mimetype="application/vnd.marimo+traceback",
        )
    else:
        sys.stderr.write(traceback)


def is_code_highlighting(value: str) -> bool:
    return 'class="codehilite"' in value
