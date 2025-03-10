# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Literal, Optional

from marimo._output.rich_help import mddoc
from marimo._runtime.context import ContextNotInitializedError, get_context
from marimo._server.model import SessionMode
from marimo._utils.assert_never import assert_never

RunMode = Literal["run", "edit", "script", "test"]


@mddoc
def running_in_notebook() -> bool:
    """Returns True if running in a marimo notebook, False otherwise"""

    try:
        ctx = get_context()
    except ContextNotInitializedError:
        return False
    else:
        from marimo._runtime.context.kernel_context import KernelRuntimeContext

        return isinstance(ctx, KernelRuntimeContext)


def get_mode() -> Optional[RunMode]:
    """Returns the current mode of the marimo app.

    Returns:
        Optional[Literal["run", "edit", "script", "test"]]: The current mode,
        or None if marimo has no context initialized.
    """
    try:
        from marimo._runtime.context.kernel_context import KernelRuntimeContext
        from marimo._runtime.context.script_context import ScriptRuntimeContext

        context = get_context()
        if isinstance(context, KernelRuntimeContext):
            if context.session_mode == SessionMode.RUN:
                return "run"
            elif context.session_mode == SessionMode.EDIT:
                return "edit"
            else:
                assert_never(context.session_mode)

        if isinstance(context, ScriptRuntimeContext):
            return "script"
    except ContextNotInitializedError:
        pass

    # This is a fallback, it's possible to be in pytest mode and have a context,
    # as in native marimo tests.
    if "PYTEST_CURRENT_TEST" in os.environ:
        return "test"

    return None
