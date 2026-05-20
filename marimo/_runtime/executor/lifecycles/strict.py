# Copyright 2026 Marimo. All rights reserved.
"""StrictLifecycle provides globals sanitization around the body."""

from __future__ import annotations

import inspect
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from marimo._ast.variables import is_mangled_local, unmangle_local
from marimo._runtime.copy import (
    CloneError,
    ShallowCopy,
    ZeroCopy,
    shallow_copy,
)
from marimo._runtime.executor.lifecycles import Skip
from marimo._runtime.primitives import (
    CLONE_PRIMITIVES,
    build_ref_predicate_for_primitives,
    from_unclonable_module,
    is_unclonable_type,
)
from marimo._runtime.runner.result import RunResult

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._messaging.errors import MarimoStrictExecutionError
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


# Attributes that should remain visible inside a strict-mode cell body
# even when the rest of the globals dict is replaced by the sanitized
# transitive references.
_PRESERVED_GLOBALS: frozenset[str] = frozenset(
    {
        "_MicropipFinder",
        "_MicropipLoader",
        "__builtin__",
        "__doc__",
        "__file__",
        "__marimo__",
        "__name__",
        "__package__",
        "__loader__",
        "__spec__",
        "input",
    }
)


class StrictLifecycle:
    """Sanitize globals before exec; restore them in teardown."""

    name = "strict"

    def __init__(self, graph: DirectedGraph) -> None:
        self._graph = graph
        # Per-cell setup→teardown backup. Keyed by cell_id.
        self._backups: dict[CellId_t, dict[str, Any]] = {}

    def setup(self, cell: CellImpl, glbls: dict[str, Any]) -> Skip | None:
        refs = self._graph.get_transitive_references(
            cell.refs,
            predicate=build_ref_predicate_for_primitives(
                glbls, CLONE_PRIMITIVES
            ),
        )

        lcls = {key: glbls[key] for key in _PRESERVED_GLOBALS if key in glbls}

        for ref in refs:
            if ref in glbls:
                lcls[ref] = self._sanitize_ref(ref, glbls[ref])
            elif ref not in glbls["__builtins__"]:
                err = self._build_strict_error(cell, ref)
                return Skip(result=RunResult(output=err, exception=err))

        # Execution expects the globals dictionary by memory reference,
        # so clear it and update with the sanitized locals, stashing a
        # backup for teardown.
        backup = {**glbls}
        glbls.clear()
        glbls.update(lcls)
        self._backups[cell.cell_id] = backup
        return None

    def _build_strict_error(
        self, cell: CellImpl, ref: str
    ) -> MarimoStrictExecutionError:
        """Produce the user-facing error for an unresolved ref in setup."""
        from marimo._messaging.errors import MarimoStrictExecutionError

        if ref in cell.defs:
            return MarimoStrictExecutionError(
                f"name `{ref}` is referenced before definition.", ref, None
            )
        blamed_cell: CellId_t | None = None
        try:
            (blamed_cell, *_) = self._graph.get_defining_cells(ref)
        except (KeyError, ValueError):
            ref, var_cell_id = unmangle_local(ref)
            if var_cell_id:
                blamed_cell = var_cell_id
        return MarimoStrictExecutionError(
            f"marimo was unable to resolve a reference to `{ref}` in cell : ",
            ref,
            blamed_cell,
        )

    def _sanitize_ref(self, name: str, value: Any) -> Any:
        if (
            isinstance(value, ZeroCopy)
            or inspect.ismodule(value)
            or inspect.isfunction(value)
            or from_unclonable_module(value)
            or is_unclonable_type(value)
        ):
            return value
        if isinstance(value, ShallowCopy):
            return shallow_copy(value)
        try:
            return deepcopy(value)
        except TypeError as e:
            raise CloneError(
                f"Could not clone reference `{name}` of type "
                f"{getattr(value, '__module__', '<module>')}. "
                f"{value.__class__.__name__} "
                "try wrapping the object in a `zero_copy` "
                "call. If this is a common object type, consider "
                "making an issue on the marimo GitHub "
                "repository to never deepcopy."
            ) from e

    def teardown(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        run_result: RunResult,  # noqa: ARG002
    ) -> None:
        backup = self._backups.pop(cell.cell_id, None)
        if backup is None:
            # Setup didn't complete for this cell (raised before stashing
            # the backup, or a Skip earlier in the chain meant setup
            # never ran). Nothing to restore.
            return

        # Restore the pre-execution globals, then re-apply the cell's
        # new defs over top.
        lcls = {**glbls}
        glbls.clear()
        glbls.update(backup)

        defs = cell.defs
        for df in defs:
            if df in lcls:
                glbls[df] = lcls[df]
            elif df in glbls:
                # Previously defined by this cell, not redefined this
                # run — stale, flush it.
                del glbls[df]

        # Flush all private variables for this cell from the restored
        # backup.
        for df in backup:
            if is_mangled_local(df, cell.cell_id):
                del glbls[df]

        # Repopulate this cell's private variables.
        for df in lcls:
            if is_mangled_local(df, cell.cell_id):
                glbls[df] = lcls[df]
