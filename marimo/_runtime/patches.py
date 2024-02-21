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


def patch_sys_module(module: types.ModuleType) -> None:
    sys.modules[module.__name__] = module


def patch_main_module(
    file: str | None, input_override: Callable[[Any], str] | None
) -> types.ModuleType:
    """Patches __main__ so that functions are pickleable."""

    # Every kernel gets its own main module, whose __dict__ attribute
    # serves as the global namespace
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

    # TODO(akshayka): In run mode, this can introduce races between different
    # kernel threads, since they each share sys.modules. Unfortunately, Python
    # doesn't provide a way for different threads to have their own sys.modules
    # (replacing the dict with a new one isn't guaranteed to have the intended
    # effect, since CPython C code has a reference to the original dict).
    # In practice, as far as I can tell, this only causes problems when using
    # Python pickle, but there may be other subtle issues.
    #
    # As a workaround, the runtime can re-patch sys.modules() on each run,
    # but the issue will still persist as a race condition. Streamlit suffers
    # from the same issue.
    patch_sys_module(_module)
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
