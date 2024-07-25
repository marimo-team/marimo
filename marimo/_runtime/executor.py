# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
import numbers
import re
import weakref
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable, Optional, Type

from marimo._ast.cell import CellImpl, _is_coroutine
from marimo._runtime.copy import (
    CloneError,
    ShallowCopy,
    ZeroCopy,
    shallow_copy,
)
from marimo._utils.variables import is_mangled_local, unmangle_local

if TYPE_CHECKING:
    from marimo._ast.visitor import Name, VariableData
    from marimo._runtime.dataflow import DirectedGraph


UNCLONABLE_TYPES = [
    "marimo._runtime.state.State",
    "marimo._runtime.state.SetFunctor",
]

UNCLONABLE_MODULES = set(
    [
        "_asyncio",
        "_io",
        "marimo._ast",
        "marimo._plugins.ui",
        "numpy.lib.npyio",
    ]
)
PRIMITIVES = (weakref.ref, str, numbers.Number, type(None))

EXECUTION_TYPES: dict[str, Type[Executor]] = {}


class MarimoRuntimeException(BaseException):
    """Wrapper for all marimo runtime exceptions."""


class MarimoNameError(NameError):
    """Wrap a name error to rethrow later."""

    def __init__(self, msg: str, ref: str) -> None:
        super().__init__(msg)
        self.ref = ref


class MarimoMissingRefError(BaseException):
    def __init__(
        self, ref: str, name_error: Optional[NameError] = None
    ) -> None:
        super(MarimoMissingRefError, self).__init__(ref)
        self.ref = ref
        self.name_error = name_error


def raise_name_error(
    graph: Optional[DirectedGraph], name_error: NameError
) -> None:
    if graph is None:
        raise MarimoRuntimeException from name_error
    # The best static analysis can do for variable level references is to
    # use the top level definition. For example, consider the following
    # cells:
    # --- Cell 1 ---
    # >> X = 1
    # >> Y = 2
    # >> l = lambda x: x + X
    # >> L = l # Static analysis can fail on reassignment
    # >> l = lambda x: x + Y
    #
    # --- Cell 2 ---
    # >> L(1) # This fails because:
    #    globals == {'Y': 2, 'l': lambda x: x + Y, 'L': lambda x: x + X}
    #    # note no X
    #
    # The code could be taken to use the last definition of `l`, but theres
    # the case of condition definition and dynamic definition, so making a
    # best effort and resolving the error at runtime is the best approach.
    #
    # marimo lint (#1543) could potentially detect these runtime
    # problems. Throwing a compilation error seems excessive since if
    # carefully managed, the code could still be correct.
    (missing_name,) = re.findall(r"'([^']*)'", str(name_error))
    _, private_cell_id = unmangle_local(missing_name)
    if missing_name in graph.definitions or private_cell_id:
        raise MarimoRuntimeException from MarimoMissingRefError(
            missing_name, name_error
        )
    raise MarimoRuntimeException from name_error


def register_execution_type(
    key: str,
) -> Callable[[Type[Executor]], Type[Executor]]:
    # Potentially expose as part of custom kernel API
    def wrapper(cls: Type[Executor]) -> Type[Executor]:
        EXECUTION_TYPES[key] = cls
        return cls

    return wrapper


async def execute_cell_async(
    cell: CellImpl,
    glbls: dict[str, Any],
    graph: DirectedGraph,
    execution_type: str = "relaxed",
) -> Any:
    return await EXECUTION_TYPES[execution_type].execute_cell_async(
        cell, glbls, graph
    )


def execute_cell(
    cell: CellImpl,
    glbls: dict[str, Any],
    graph: DirectedGraph,
    execution_type: str = "relaxed",
) -> Any:
    return EXECUTION_TYPES[execution_type].execute_cell(cell, glbls, graph)


class Executor(ABC):
    @staticmethod
    @abstractmethod
    def execute_cell(
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        pass

    @staticmethod
    @abstractmethod
    async def execute_cell_async(
        cell: CellImpl,
        glbls: dict[str, Any],
        graph: DirectedGraph,
    ) -> Any:
        pass


@register_execution_type("relaxed")
class DefaultExecutor(Executor):
    @staticmethod
    async def execute_cell_async(
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
            raise_name_error(graph, e)
        except (BaseException, Exception) as e:
            # Raising from a BaseException will fold in the stacktrace prior
            # to execution
            raise MarimoRuntimeException from e

    @staticmethod
    def execute_cell(
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
            raise_name_error(graph, e)
        except (BaseException, Exception) as e:
            raise MarimoRuntimeException from e


@register_execution_type("strict")
class StrictExecutor(Executor):
    @staticmethod
    async def execute_cell_async(
        cell: CellImpl, glbls: dict[str, Any], graph: DirectedGraph
    ) -> Any:
        # Manage globals and references, but refers to the default beyond that.
        refs = graph.get_transitive_references(
            cell.refs, predicate=build_ref_predicate(glbls)
        )
        backup = StrictExecutor.sanitize_inputs(cell, refs, glbls)
        try:
            response = await DefaultExecutor.execute_cell_async(
                cell, glbls, graph
            )
        finally:
            # Restore globals from backup and backfill outputs
            StrictExecutor.update_outputs(cell, glbls, backup)
        return response

    @staticmethod
    def execute_cell(
        cell: CellImpl, glbls: dict[str, Any], graph: DirectedGraph
    ) -> Any:
        refs = graph.get_transitive_references(
            cell.refs, predicate=build_ref_predicate(glbls)
        )
        backup = StrictExecutor.sanitize_inputs(cell, refs, glbls)
        try:
            response = DefaultExecutor.execute_cell(cell, glbls, graph)
        finally:
            StrictExecutor.update_outputs(cell, glbls, backup)
        return response

    @staticmethod
    def sanitize_inputs(
        cell: CellImpl, refs: set[str], glbls: dict[str, Any]
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
                            f"{getattr(glbls[ref], '__module__', '<module>')}."
                            f"{glbls[ref].__class__.__name__}"
                            " try wrapping the object in a `zero_copy`"
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

    @staticmethod
    def update_outputs(
        cell: CellImpl, glbls: dict[str, Any], backup: dict[str, Any]
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


def build_ref_predicate(
    glbls: dict[str, Any],
) -> Callable[[Name, VariableData], bool]:
    """
    Builds a predicate function to determine if a reference should be included

    Args:
        glbls: The global variables dictionary to base the predicate on
    Returns:
        A function that takes a variable name and associated data and
        returns True if its reference should be included in a reference search.

    All declared variables are tied together under the graph of required_refs.
    Strict execution gets the minimum graph of definitions for execution.
    Certain definitions, like lambdas, functions, and classes contain an
    executable body and require their `required_refs` to be scope (included in
    this graph). This function determines if a potential reference should be
    included in the graph based on its computed type. Consider:

    >>> def foo():
    ...     return bar()

    here `foo` is a function with `bar` as a reference in the execution body,
    so if `foo` is a reference, both `bar` and `foo` should be included in the
    graph, otherwise we'll get a NameError on `bar` if `foo` is called.
    Compare that to:

    >>> x = foo()

    if `x` is the only reference, should `foo` be included in the graph? It
    depends on the context, so we defer to the type of `x` which has already
    been computed at this point. If `x` is a known 'primitive' type, and thus
    does not have an executable body, we can exclude `foo` from the graph.
    However, `foo` may return a object or another function, which in turn may
    have references; so if x doesn't match the very low bar 'primitive', its
    `required_refs` are included in the graph.

    NB: lambdas, as anonymous functions, do not have a name to refer to them-
    so visitor injects the dummy variable `_lambda` into the `required_refs` to
    denote their presence.
    """

    def check_ref(ref: Name) -> bool:
        return ref in glbls and (
            inspect.isfunction(glbls[ref])
            or inspect.ismodule(glbls[ref])
            or inspect.isclass(glbls[ref])
            or callable(glbls[ref])
        )

    def only_scoped_refs(ref: Name, data: VariableData) -> bool:
        # Weakref instances should be disassociated from related references,
        # as should other "primitives" as they are results and hopefully not
        # hiding some scoped reference. Other common types could be added here,
        # like numpy arrays that are not dtype=object, etc.. that are known not
        # to be dependent on the functions that created them.

        # This errs on the side of including too much, but that's a better user
        # experience than not having definitions available.
        return (
            ref in glbls
            and not isinstance(glbls[ref], PRIMITIVES)
            and (
                "_lambda" in data.required_refs
                or any(map(check_ref, data.required_refs | {ref}))
            )
        )

    return only_scoped_refs


def is_instance_by_name(obj: object, name: str) -> bool:
    if not (hasattr(obj, "__module__") and hasattr(obj, "__class__")):
        return False
    obj_name = f"{obj.__module__}.{obj.__class__.__name__}"
    return obj_name == name


def is_unclonable_type(obj: object) -> bool:
    return any([is_instance_by_name(obj, name) for name in UNCLONABLE_TYPES])


def from_unclonable_module(obj: object) -> bool:
    obj = obj if hasattr(obj, "__module__") else obj.__class__
    return hasattr(obj, "__module__") and any(
        [obj.__module__.startswith(name) for name in UNCLONABLE_MODULES]
    )
