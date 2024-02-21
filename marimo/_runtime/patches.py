# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import contextlib
import functools
import sys
import types
from typing import Any, Callable, Iterator

from marimo._runtime import marimo_pdb


def patch_pdb(debugger: marimo_pdb.MarimoPdb) -> None:
    import pdb

    # Patch Pdb so manually instantiated debuggers create our debugger
    pdb.Pdb = marimo_pdb.MarimoPdb  # type: ignore[misc, assignment]
    pdb.set_trace = functools.partial(marimo_pdb.set_trace, debugger=debugger)


def patch_main_module(
    file: str | None, input_override: Callable[[Any], str] | None
) -> types.ModuleType:
    """Patches __main__ so that functions are pickleable."""

    _module = types.ModuleType(
        "__main__", doc="Created for the marimo kernel."
    )
    _module.__dict__.setdefault("__builtin__", globals()["__builtins__"])
    _module.__dict__.setdefault("__builtins__", globals()["__builtins__"])

    if input_override is not None:
        _module.__dict__.setdefault("input", input_override)

    if file is not None:
        _module.__dict__.setdefault("__file__", file)
    else:
        _module.__dict__.setdefault(
            "__file__", sys.modules["__main__"].__file__
        )

    sys.modules[_module.__name__] = _module
    return _module


@contextlib.contextmanager
def patch_main_module_context(
    file: str | None = None, input_override: Callable[[Any], str] | None = None
) -> Iterator[types.ModuleType]:
    main = sys.modules["__main__"]
    try:
        yield patch_main_module(file, input_override)
    finally:
        sys.modules["__main__"] = main
