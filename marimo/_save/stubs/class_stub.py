# Copyright 2026 Marimo. All rights reserved.
"""ClassStub — source-based serialization for cell-defined classes.

Pickle stores a class reference as ``(__module__, __qualname__)``. For
classes defined inside marimo cells the module is ``"__main__"``, but the
interpreter's ``sys.modules["__main__"]`` does not actually hold the cell
namespace — so ``pickle.loads`` of a cell-defined class (or an instance of
one) fails with ``AttributeError: Can't get attribute 'KAN' on <module
'__main__' ...>``.

``ClassStub`` mirrors the role of :class:`FunctionStub` for classes:
capture the class source at save time, re-exec the source into the cell
namespace at load time. Once the class is alive in the namespace,
:class:`~marimo._save.loaders.unpickler.CellNamespaceUnpickler` can
resolve ``__main__.KAN`` against that namespace instead of
``sys.modules["__main__"]``.
"""

from __future__ import annotations

import inspect
import linecache
import textwrap
from typing import Any

__all__ = ["ClassStub"]


class ClassStub:
    """Stub for class objects, storing the source code."""

    def __init__(self, cls: Any) -> None:
        self.qualname = cls.__qualname__
        # Classes don't have their own ``__code__``/``co_filename`` like
        # functions do — they rely on ``__module__`` to find the source
        # file. For cell-defined classes ``__module__`` is ``'__main__'``
        # which (in marimo's cell glbls) points at the kernel process
        # binary, not the cell. Bypass ``inspect.getfile`` by reading the
        # filename off any defined method's ``__code__.co_filename`` —
        # that's the file (or marimo cell ID) the class was compiled in.
        filename = self._find_filename(target=cls)
        if filename is None:
            # Fallback: trust inspect.getsource and hope ``__module__``
            # resolves. Raises if the class is unsourcable.
            self.code = textwrap.dedent(inspect.getsource(cls))
            self.filename = f"<{cls.__name__}>"
            self.lineno = 1
            try:
                self.filename = inspect.getfile(cls)
                _, self.lineno = inspect.getsourcelines(cls)
            except (TypeError, OSError):
                pass
            return

        lines = linecache.getlines(filename)
        if not lines:
            raise OSError(
                f"No source available for {cls.__name__} in {filename!r}"
            )
        lineno = vars(cls).get("__firstlineno__")
        if lineno is None:
            # Older Python: scan for the class statement by name.
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
        self.filename = filename
        self.lineno = lineno

    @staticmethod
    def _find_filename(target: Any) -> str | None:
        """Return the source filename for *target* by inspecting a
        defined method's ``__code__.co_filename``, or ``None`` if no
        method has a code object (e.g. ``type(...)``-built classes)."""
        for attr in vars(target).values():
            code = getattr(attr, "__code__", None)
            if code is not None:
                filename: str = code.co_filename
                return filename
        return None

    def load(self, glbls: dict[str, Any]) -> Any:
        """Reconstruct the class by executing its source in *glbls*.

        For synthetic filenames (``"<ClassName>"``), seed ``linecache``
        so tracebacks render the source. For real filenames, leave
        ``linecache`` alone and trust Python's normal lookup.
        """
        if self.filename.startswith("<"):
            linecache.cache[self.filename] = (
                len(self.code),
                None,
                [line + "\n" for line in self.code.splitlines()],
                self.filename,
            )

        code_obj = compile(self.code, self.filename, "exec")
        # Exec into glbls directly so the class lands in the cell
        # namespace under its bare name. (We intentionally do not pass an
        # lcls dict — top-level class statements must execute against
        # glbls for cross-cell references to bind correctly.)
        exec(code_obj, glbls)
        # Return the class object the source defined. The qualname's
        # final segment is the class name as bound in glbls.
        bare_name = self.qualname.rsplit(".", 1)[-1]
        return glbls.get(bare_name)

    def dump(self) -> tuple[str, str, int, str]:
        """Dump source + metadata for lazy serialization."""
        return self.code, self.filename, self.lineno, self.qualname

    @classmethod
    def from_dump(cls, dump: tuple[str, str, int, str]) -> ClassStub:
        """Reconstruct a ``ClassStub`` from a ``dump()`` tuple.

        Skips ``__init__`` (which requires a live class to introspect).
        """
        stub = cls.__new__(cls)
        stub.code, stub.filename, stub.lineno, stub.qualname = dump
        return stub
