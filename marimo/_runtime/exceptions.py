# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._runtime.dataflow import DirectedGraph


class MarimoRuntimeException(BaseException):
    """Wrapper for all marimo runtime exceptions."""


class MarimoNameError(NameError):
    """Wrap a name error to rethrow later."""

    def __init__(self, msg: str, ref: str) -> None:
        super().__init__(msg)
        self.ref = ref


class MarimoMissingRefError(BaseException):
    def __init__(self, ref: str, name_error: NameError | None = None) -> None:
        super().__init__(ref)
        self.ref = ref
        self.name_error = name_error


def unwrap_user_exception(
    exc: MarimoRuntimeException,
    graph: DirectedGraph | None = None,
) -> BaseException | None:
    """Extract the user exception from a ``MarimoRuntimeException``."""
    cause = exc.__cause__
    if graph is not None and isinstance(cause, NameError):
        name = getattr(cause, "name", None)
        if name and name in graph.definitions:
            return MarimoMissingRefError(name, cause)
    return cause
