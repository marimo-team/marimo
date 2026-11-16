# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations
import __future__

import ast
import functools
import inspect
import linecache
import operator
import sys
import textwrap
from typing import Any

__all__ = ["FUTURE_FLAGS", "FunctionStub"]

# Compiler flags of the __future__ features still optional in this
# interpreter. A mandatory feature is always on, and its bit can mean
# something else: nested_scopes shares CO_NESTED.
FUTURE_FLAGS = functools.reduce(
    operator.or_,
    (
        feature.compiler_flag
        for feature in (
            getattr(__future__, name) for name in __future__.all_feature_names
        )
        if feature.getMandatoryRelease() is None
        or feature.getMandatoryRelease() > sys.version_info
    ),
    0,
)


class FunctionStub:
    """Stub for function objects, storing the source code.

    `@mo.cache` / `@mo.persistent_cache` wrappers are special-cased and recorded
    in `is_cached`, which allows lazier restoration of the wrapper.
    """

    def __init__(self, function: Any, is_cached: bool = False) -> None:
        self.is_cached = is_cached
        if is_cached:
            # Capture the wrapped body's source (incl. the decorator line).
            function = function.__wrapped__
        self.code = textwrap.dedent(inspect.getsource(function))
        self.filename = f"<{function.__name__}>"
        self.lineno = 1
        # The snippet holds the definition alone, not the module's
        # `from __future__` imports that governed it. The flags come from the
        # same function `getsource` read: a decorator's wrapper may differ.
        self.flags = inspect.unwrap(function).__code__.co_flags & FUTURE_FLAGS
        # Restored at top level, the function would otherwise lose the class
        # that keys it. Both names: `functools.wraps` copies the function's
        # qualname, which pickling by reference needs, but not the code's,
        # which keys it.
        self.qualname = function.__qualname__
        self.code_qualname = function.__code__.co_qualname
        if is_cached:
            # NB. keep the synthetic filename: the wrapper re-hashes its own
            # source per call, and the real path is absent on restore.
            return

        try:
            self.filename = inspect.getfile(function)
            _, self.lineno = inspect.getsourcelines(function)
        except (TypeError, OSError):
            pass

    def load(self, glbls: dict[str, Any]) -> Any:
        """Reconstruct the function by executing its source code."""
        fragment = [line + "\n" for line in self.code.splitlines()]
        filename = self.filename
        on_disk: list[str] = []
        if not filename.startswith("<"):
            linecache.checkcache(filename)
            on_disk = linecache.getlines(filename)
        window = on_disk[self.lineno - 1 : self.lineno - 1 + len(fragment)]
        if not window or textwrap.dedent("".join(window)) != self.code:
            # The file belongs to another process, or has shifted since.
            # Serve the stored source under a name of its own, at its
            # original line, so the restored function hashes like the
            # definition it stands in for.
            if not filename.startswith("<"):
                filename = f"<{filename}:{self.lineno}>"
            lines = ["\n"] * (self.lineno - 1) + fragment
            linecache.cache[filename] = (len(self.code), None, lines, filename)

        tree = ast.increment_lineno(ast.parse(self.code), self.lineno - 1)
        # The snippet's own future flags and no others: not this module's,
        # which `compile` would inherit.
        code_obj = compile(
            tree, filename, "exec", flags=self.flags, dont_inherit=True
        )
        lcls: dict[str, Any] = {}
        exec(code_obj, glbls, lcls)
        for value in lcls.values():
            if inspect.isfunction(value):
                value.__qualname__ = self.qualname
                value.__code__ = value.__code__.replace(
                    co_qualname=self.code_qualname
                )
            return value

    def dump(self) -> tuple[str, str, int, bool, int, str, str]:
        """Dump stored source code and metadata for lazy serialization."""
        return (
            self.code,
            self.filename,
            self.lineno,
            self.is_cached,
            self.flags,
            self.qualname,
            self.code_qualname,
        )

    @classmethod
    def from_dump(
        cls, data: tuple[str, str, int, bool, int, str, str]
    ) -> FunctionStub:
        """Reconstruct a `FunctionStub` from a `dump()` tuple.

        Skips `__init__` (which requires a live function to introspect).
        """
        stub = cls.__new__(cls)
        (
            stub.code,
            stub.filename,
            stub.lineno,
            stub.is_cached,
            stub.flags,
            stub.qualname,
            stub.code_qualname,
        ) = data
        return stub
