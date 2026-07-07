# Copyright 2026 Marimo. All rights reserved.
"""ClassStub — source-based serialization for cell-defined classes.

Pickle stores a class reference as `(__module__, __qualname__)`. For
classes defined inside marimo cells the module is `"__main__"`, and dynamicall
patched into the runtime.
"""

from __future__ import annotations

import inspect
import linecache
import textwrap
from typing import Any

__all__ = ["ClassStub"]


class ClassStub:
    """Stub for class objects, storing the source code."""

    def __init__(self, cls: Any, filename: str | None = None) -> None:
        self.qualname = cls.__qualname__
        # Classes don't have their own `__code__`/`co_filename` like
        # functions do — they rely on `__module__` to find the source
        # file.
        method_code = self._find_code(target=cls)
        if method_code is None and filename is None:
            # Fallback: trust inspect.getsource. Raises if unsourcable.
            self.code = textwrap.dedent(inspect.getsource(cls))
            return

        filename = (
            method_code.co_filename if method_code is not None else filename
        )
        if filename is None:
            raise ValueError("No filename, invalid load")

        lines = linecache.getlines(filename)
        if not lines:
            raise OSError(
                f"No source available for {cls.__name__} in {filename!r}"
            )
        lineno = vars(cls).get("__firstlineno__")
        if lineno is None and method_code is not None:
            # Older Python (no `__firstlineno__`): anchor on the class's own
            # method, scanning upward from its line to the nearest enclosing
            # `class <name>` statement. Tying the lineno to a real code object
            # of *this* class avoids matching a same-named earlier (redefined)
            # class higher in the file.
            for idx in range(
                min(method_code.co_firstlineno, len(lines)) - 1, -1, -1
            ):
                if lines[idx].lstrip().startswith(f"class {cls.__name__}"):
                    lineno = idx + 1
                    break
        if lineno is None:
            # Last resort (no method code object): forward scan by name.
            for idx, line in enumerate(lines):
                if line.lstrip().startswith(f"class {cls.__name__}"):
                    lineno = idx + 1
                    break
        if lineno is None:
            raise OSError(
                f"Could not locate class {cls.__name__} in {filename!r}"
            )
        block = inspect.getblock(lines[lineno - 1 :])
        self.code = textwrap.dedent("".join(block))

    @staticmethod
    def _find_code(target: Any) -> Any:
        """Return a `__code__` object from a callable defined on *target*,
        or `None` if none is found (e.g. `type(...)`-built or attribute-only
        classes). Unwraps descriptor-wrapped callables — `staticmethod`,
        `classmethod`, and `property` — which don't expose `__code__`
        directly, so classes defining only those still resolve a filename."""
        for attr in vars(target).values():
            code = getattr(attr, "__code__", None)
            if code is None:
                func = getattr(attr, "__func__", None) or getattr(
                    attr, "fget", None
                )
                code = getattr(func, "__code__", None)
            if code is not None:
                return code
        return None

    def load(self, glbls: dict[str, Any]) -> Any:
        """Reconstruct the class by executing its source in *glbls*.

        The filename is derived from the loading cell (see
        `_load_filename`); `linecache` is seeded under that class-specific
        key so tracebacks render the source without clobbering the cell's
        own entry.
        """
        bare_name = self.qualname.rsplit(".", 1)[-1]
        filename = self._load_filename(bare_name)
        linecache.cache[filename] = (
            len(self.code),
            None,
            [line + "\n" for line in self.code.splitlines()],
            filename,
        )
        # Exec into glbls directly so the class lands in the cell namespace
        # under its bare name. (No lcls dict — top-level class statements
        # must execute against glbls for cross-cell references to bind.)
        #
        # On a cache hit glbls is the cell namespace, i.e.
        # `sys.modules["__main__"].__dict__`, so this also registers the
        # class as `__main__.<name>` — which is exactly what `pickle.loads`
        # uses to resolve instances of it (no custom unpickler needed).
        exec(compile(self.code, filename, "exec"), glbls)
        return glbls.get(bare_name)

    @staticmethod
    def _load_filename(bare_name: str) -> str:
        """Filename for compiling the class source: the *loading* cell's
        file when a kernel context exists, else a synthetic name. Suffixed
        by the class name so seeding `linecache` does not overwrite the
        cell's own source entry."""
        try:
            from marimo._ast.compiler import get_filename
            from marimo._runtime.context import (
                ContextNotInitializedError,
                get_context,
            )

            ctx = get_context().execution_context
            if ctx is not None:
                return get_filename(ctx.cell_id, suffix=bare_name)
        except (ContextNotInitializedError, AssertionError):
            pass
        return f"<{bare_name}>"

    def dump(self) -> tuple[str, str]:
        """Dump source + qualname for lazy serialization."""
        return self.code, self.qualname

    @classmethod
    def from_dump(cls, dump: tuple[str, str]) -> ClassStub:
        """Reconstruct a `ClassStub` from a `dump()` tuple.

        Skips `__init__` (which requires a live class to introspect).
        """
        stub = cls.__new__(cls)
        stub.code, stub.qualname = dump
        return stub
