# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._output.rich_help import mddoc

# We used to define a custom MarimoInterrupt BaseException to interrupt the
# kernel; however, some third-party libraries like databricks-connect have
# special case handling of KeyboardInterrupt.
MarimoInterrupt = KeyboardInterrupt


class MarimoStopError(BaseException):
    """Raised by `marimo.stop` to stop execution of a cell and descendants.

    Inherits from `BaseException` to prevent accidental capture with
    `except Exception` (similar to `KeyboardInterrupt`)
    """

    def __init__(self, output: Optional[object]) -> None:
        self.output = output


@mddoc
def stop(predicate: bool, output: Optional[object] = None) -> None:
    """Stops execution of a cell when `predicate` is `True`

    When `predicate` is `True`, this function raises a `MarimoStopError`. If
    uncaught, this exception stops execution of the current cell and makes
    `output` its output. Any descendants of this cell that were previously
    scheduled to run will not be run, and their defs will be removed from
    program memory.

    Examples:
        ```python
        mo.stop(form.value is None, mo.md("**Submit the form to continue.**"))
        ```

    Raises:
        MarimoStopError: When `predicate` is `True`
    """
    if predicate:
        raise MarimoStopError(output)
