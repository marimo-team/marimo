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
        # When stderr is not redirected (e.g., run mode with redirect_console_to_browser=False),
        # send the traceback directly via the stream to ensure exceptions reach the frontend
        from marimo._messaging.cell_output import CellChannel, CellOutput
        from marimo._messaging.notification import CellNotification
        from marimo._messaging.notification_utils import broadcast_notification
        from marimo._runtime.context.types import safe_get_context

        ctx = safe_get_context()
        if ctx is not None and ctx.cell_id is not None:
            broadcast_notification(
                CellNotification(
                    cell_id=ctx.cell_id,
                    console=CellOutput(
                        channel=CellChannel.STDERR,
                        mimetype="application/vnd.marimo+traceback",
                        data=_highlight_traceback(_trim_traceback(traceback)),
                    ),
                ),
                ctx.stream,
            )
        else:
            # Fallback to regular stderr if no context is available
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
