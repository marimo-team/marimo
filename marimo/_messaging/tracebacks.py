# Copyright 2026 Marimo. All rights reserved.
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
            _highlight_traceback(_trim_traceback(traceback)),
            mimetype="application/vnd.marimo+traceback",
        )
    else:
        sys.stderr.write(traceback)


def _trim_traceback(traceback: str) -> str:
    """
    Skip first DefaultExecutor.execute_cell traceback item which all traces start with.
    """

    lines = traceback.split("\n")
    if (
        len(lines) > 2
        and lines[0] == "Traceback (most recent call last):"
        and '/marimo/_runtime/executor.py", line ' in lines[1]
        and lines[1].endswith(", in execute_cell")
    ):
        for i in range(2, len(lines)):
            if lines[i].startswith("  File "):
                return "\n".join(lines[:1] + lines[i:])

    return traceback


def is_code_highlighting(value: str) -> bool:
    return 'class="codehilite"' in value
