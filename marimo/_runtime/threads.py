import threading

from marimo._runtime.context.types import (
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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if runtime_context_installed():
            self._marimo_ctx = get_context()
        else:
            self._marimo_ctx = None

    def run(self):
        if self._marimo_ctx is not None:
            initialize_context(self._marimo_ctx)
        super().run()
