# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.context import is_code_mode_request
from marimo._messaging.notification import CellNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._messaging.types import Stderr
from marimo._runtime.context.types import safe_get_context
from marimo._runtime.context.utils import get_mode


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


def _show_tracebacks_enabled() -> bool:
    """Returns True if show_tracebacks is enabled in the current config."""
    from marimo._runtime.context.types import (
        ContextNotInitializedError,
        get_context,
    )

    try:
        ctx = get_context()
        return bool(ctx.marimo_config["runtime"].get("show_tracebacks", False))
    except ContextNotInitializedError:
        return True  # no context → not in run mode, always show


def write_traceback(traceback: str) -> None:
    in_run_mode = get_mode() == "run"
    code_mode = is_code_mode_request()

    if isinstance(sys.stderr, Stderr) and not code_mode:
        # In run mode, only forward to the frontend if show_tracebacks is on.
        if in_run_mode and not _show_tracebacks_enabled():
            return
        sys.stderr._write_with_mimetype(
            _highlight_traceback(traceback),
            mimetype="application/vnd.marimo+traceback",
        )
    else:
        # When stderr is not redirected (e.g., run mode with redirect_console_to_browser=False),
        # send the traceback directly via the stream to ensure exceptions reach the frontend
        ctx = safe_get_context()
        if ctx is not None and ctx.cell_id is not None:
            # In run mode, only forward to the frontend if show_tracebacks is on.
            if in_run_mode and not _show_tracebacks_enabled():
                sys.stderr.write(traceback)
                return
            broadcast_notification(
                CellNotification(
                    cell_id=ctx.cell_id,
                    console=CellOutput(
                        channel=CellChannel.STDERR,
                        mimetype="application/vnd.marimo+traceback",
                        data=traceback
                        if code_mode
                        else _highlight_traceback(traceback),
                    ),
                ),
                ctx.stream,
            )
        else:
            # Fallback to regular stderr if no context is available
            sys.stderr.write(traceback)


def is_code_highlighting(value: str) -> bool:
    return 'class="codehilite"' in value
