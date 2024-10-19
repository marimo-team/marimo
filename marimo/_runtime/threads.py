# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import threading
from typing import Any

from marimo._runtime.context.types import (
    RuntimeContext,
    get_context,
    initialize_context,
    runtime_context_installed,
)


class Thread(threading.Thread):
    """A Thread subclass that is aware of marimo internals.

    `mo.Thread` has the same API as threading.Thread,
    but `mo.Thread`s are able to communicate with the marimo
    frontend, whereas `threading.Thread` can't.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._marimo_ctx: RuntimeContext | None = None

        if runtime_context_installed():
            self._marimo_ctx = get_context()

    def run(self) -> None:
        if self._marimo_ctx is not None:
            initialize_context(self._marimo_ctx)
        super().run()
