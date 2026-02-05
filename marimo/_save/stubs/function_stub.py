# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import textwrap
from typing import Any

__all__ = ["FunctionStub"]


class FunctionStub:
    """Stub for function objects, storing the source code."""

    def __init__(self, function: Any) -> None:
        self.code = textwrap.dedent(inspect.getsource(function))

    def load(self, glbls: dict[str, Any]) -> Any:
        """Reconstruct the function by executing its source code."""
        # TODO: Fix line cache and associate with the correct module.
        code_obj = compile(self.code, "<string>", "exec")
        lcls: dict[str, Any] = {}
        exec(code_obj, glbls, lcls)
        # Update the global scope with the function.
        for value in lcls.values():
            return value
