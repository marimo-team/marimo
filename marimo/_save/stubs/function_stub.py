# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import linecache
import textwrap
from typing import Any

__all__ = ["FunctionStub"]


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
        if self.filename.startswith("<"):
            linecache.cache[self.filename] = (
                len(self.code),
                None,
                [line + "\n" for line in self.code.splitlines()],
                self.filename,
            )

        code_obj = compile(self.code, self.filename, "exec")
        lcls: dict[str, Any] = {}
        exec(code_obj, glbls, lcls)
        for value in lcls.values():
            return value

    def dump(self) -> tuple[str, str, int, bool]:
        """Dump stored source code and metadata for lazy serialization."""
        return self.code, self.filename, self.lineno, self.is_cached

    @classmethod
    def from_dump(cls, data: tuple[str, str, int, bool]) -> FunctionStub:
        """Reconstruct a `FunctionStub` from a `dump()` tuple.

        Skips `__init__` (which requires a live function to introspect).
        """
        stub = cls.__new__(cls)
        stub.code, stub.filename, stub.lineno, stub.is_cached = data
        return stub
