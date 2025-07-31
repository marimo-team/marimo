# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from marimo._ast.cell import CellImpl, _is_coroutine
from marimo._ast.variables import is_mangled_local, unmangle_local
from marimo._entrypoints.registry import EntryPointRegistry
from marimo._runtime.copy import (
    CloneError,
    ShallowCopy,
    ZeroCopy,
    shallow_copy,
)
from marimo._runtime.exceptions import (
    MarimoMissingRefError,
    MarimoNameError,
    MarimoRuntimeException,
)
from marimo._runtime.primitives import (
    CLONE_PRIMITIVES,
    build_ref_predicate_for_primitives,
    from_unclonable_module,
    is_unclonable_type,
)

if TYPE_CHECKING:
    from marimo._runtime.dataflow import DirectedGraph

_EXECUTOR_REGISTRY = EntryPointRegistry[type["Executor"]](
    "marimo.cell.executor",
)


def get_executor(
    config: ExecutionConfig,
    registry: EntryPointRegistry[type[Executor]] = _EXECUTOR_REGISTRY,
) -> Executor:
    """Get a code executor based on the execution configuration."""
    executors = registry.get_all()

    base: Executor = DefaultExecutor()
    if config.is_strict:
        base = StrictExecutor(base)

    for executor in executors:
        base = executor(base)
    return base


@dataclass
class ExecutionConfig:
    """Configuration for cell execution."""

    is_strict: bool = False


def _raise_name_error(
    graph: Optional[DirectedGraph], name_error: NameError
) -> None:
    if graph is None:
        raise MarimoRuntimeException from name_error
    (missing_name,) = re.findall(r"'([^']*)'", str(name_error))
    _, private_cell_id = unmangle_local(missing_name)
    if missing_name in graph.definitions or private_cell_id:
        raise MarimoRuntimeException from MarimoMissingRefError(
            missing_name, name_error
        )
    raise MarimoRuntimeException from name_error


class Executor(ABC):
    def __init__(self, base: Optional[Executor] = None) -> None:
        self.base = base

    @abstractmethod
    def execute_cell(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        pass

    @abstractmethod
    async def execute_cell_async(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        pass


class DefaultExecutor(Executor):
    async def execute_cell_async(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: Optional[DirectedGraph] = None,
    ) -> Any:
        if cell.body is None:
            return None
        assert cell.last_expr is not None
        try:
            if _is_coroutine(cell.body):
                await eval(cell.body, glbls)
            else:
                exec(cell.body, glbls)

            if _is_coroutine(cell.last_expr):
                return await eval(cell.last_expr, glbls)
            else:
                return eval(cell.last_expr, glbls)
        except NameError as e:
            _raise_name_error(graph, e)
        except (BaseException, Exception) as e:
            # Raising from a BaseException will fold in the stacktrace prior
            # to execution
            raise MarimoRuntimeException from e

    def execute_cell(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: Optional[DirectedGraph] = None,
    ) -> Any:
        try:
            if cell.body is None:
                return None
            assert cell.last_expr is not None

            exec(cell.body, glbls)
            return eval(cell.last_expr, glbls)
        except NameError as e:
            _raise_name_error(graph, e)
        except (BaseException, Exception) as e:
            raise MarimoRuntimeException from e


class StrictExecutor(Executor):
    async def execute_cell_async(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        assert self.base is not None, "Invalid executor composition."

        # Manage globals and references, but refers to the default beyond that.
        refs = graph.get_transitive_references(
            cell.refs,
            predicate=build_ref_predicate_for_primitives(
                glbls, CLONE_PRIMITIVES
            ),
        )
        backup = self._sanitize_inputs(cell, refs, glbls)
        try:
            response = await self.base.execute_cell_async(cell, glbls, graph)
        finally:
            # Restore globals from backup and backfill outputs
            self._update_outputs(cell, glbls, backup)
        return response

    def execute_cell(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        assert self.base is not None, "Invalid executor composition."

        refs = graph.get_transitive_references(
            cell.refs,
            predicate=build_ref_predicate_for_primitives(
                glbls, CLONE_PRIMITIVES
            ),
        )
        backup = self._sanitize_inputs(cell, refs, glbls)
        try:
            response = self.base.execute_cell(cell, glbls, graph)
        finally:
            self._update_outputs(cell, glbls, backup)
        return response

    def _sanitize_inputs(
        self,
        cell: CellImpl,
        refs: set[str],
        glbls: dict[str, Any],
    ) -> dict[str, Any]:
        # Some attributes should remain global
        lcls = {
            key: glbls[key]
            for key in [
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
            ]
            if key in glbls
        }

        for ref in refs:
            if ref in glbls:
                if (
                    isinstance(
                        glbls[ref],
                        (ZeroCopy),
                    )
                    or inspect.ismodule(glbls[ref])
                    or inspect.isfunction(glbls[ref])
                    or from_unclonable_module(glbls[ref])
                    or is_unclonable_type(glbls[ref])
                ):
                    lcls[ref] = glbls[ref]
                elif isinstance(glbls[ref], ShallowCopy):
                    lcls[ref] = shallow_copy(glbls[ref])
                else:
                    try:
                        lcls[ref] = deepcopy(glbls[ref])
                    except TypeError as e:
                        raise CloneError(
                            f"Could not clone reference `{ref}` of type "
                            f"{getattr(glbls[ref], '__module__', '<module>')}. "
                            f"{glbls[ref].__class__.__name__} "
                            "try wrapping the object in a `zero_copy` "
                            "call. If this is a common object type, consider "
                            "making an issue on the marimo GitHub "
                            "repository to never deepcopy."
                        ) from e
            elif ref not in glbls["__builtins__"]:
                if ref in cell.defs:
                    raise MarimoNameError(
                        f"name `{ref}` is referenced before definition.", ref
                    )
                raise MarimoMissingRefError(ref)

        # NOTE: Execution expects the globals dictionary by memory reference,
        # so we need to clear it and update it with the sanitized locals,
        # returning a backup of the original globals for later restoration.
        # This must be performed at the end of the function to ensure valid
        # state in case of failure.
        backup = {**glbls}
        glbls.clear()
        glbls.update(lcls)
        return backup

    def _update_outputs(
        self,
        cell: CellImpl,
        glbls: dict[str, Any],
        backup: dict[str, Any],
    ) -> None:
        # NOTE: After execution, restore global state and update outputs.
        lcls = {**glbls}
        glbls.clear()
        glbls.update(backup)

        defs = cell.defs
        for df in defs:
            if df in lcls:
                # Overwrite will delete the reference.
                # Weak copy holds on with references.
                glbls[df] = lcls[df]
            # Captures the case where a variable was previously defined by the
            # cell but this most recent run did not define it. The value is now
            # stale and needs to be flushed.
            elif df in glbls:
                del glbls[df]

        # Flush all private variables from memory
        for df in backup:
            if is_mangled_local(df, cell.cell_id):
                del glbls[df]

        # Now repopulate all private variables.
        for df in lcls:
            if is_mangled_local(df, cell.cell_id):
                glbls[df] = lcls[df]
