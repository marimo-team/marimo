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
        # Strip marimo's internal executor.py frame and highlight for the UI
        trimmed = _trim_traceback(traceback)
        sys.stderr._write_with_mimetype(
            _highlight_traceback(trimmed),
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
            trimmed = _trim_traceback(traceback)
            broadcast_notification(
                CellNotification(
                    cell_id=ctx.cell_id,
                    console=CellOutput(
                        channel=CellChannel.STDERR,
                        mimetype="application/vnd.marimo+traceback",
                        data=trimmed
                        if code_mode
                        else _highlight_traceback(trimmed),
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
