# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import linecache
import textwrap
from typing import Any

__all__ = ["FunctionStub"]


class FunctionStub:
    """Stub for function objects, storing the source code."""

    def __init__(self, function: Any) -> None:
        self.code = textwrap.dedent(inspect.getsource(function))
        # Store metadata for proper source attribution
        self.module = function.__module__
        self.filename = f"<{function.__name__}>"
        self.lineno = 1

        try:
            self.filename = inspect.getfile(function)
            _, self.lineno = inspect.getsourcelines(function)
        except (TypeError, OSError):
            pass

    def load(self, glbls: dict[str, Any]) -> Any:
        """Reconstruct the function by executing its source code."""
        # If using a synthetic filename, add to linecache for getsourcelines
        if self.filename.startswith("<"):
            linecache.cache[self.filename] = (
                len(self.code),
                None,
                [line + "\n" for line in self.code.splitlines()],
                self.filename,
            )

        # Compile with the actual filename for proper tracebacks and source inspection
        code_obj = compile(self.code, self.filename, "exec")
        lcls: dict[str, Any] = {}
        exec(code_obj, glbls, lcls)
        # Update the global scope with the function.
        for value in lcls.values():
            return value

    def dump(self) -> tuple[str, str, int]:
        """Dump the stored source code and metadata."""
        return self.filename, self.code, self.lineno
