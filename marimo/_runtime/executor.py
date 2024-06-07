# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import Any, Callable, Type

from marimo._ast.cell import CellImpl, _is_coroutine
from marimo._runtime.copy import (
    CloneError,
    ShallowCopy,
    ZeroCopy,
    shallow_copy,
)

UNCLONABLE_TYPES = [
    "marimo._runtime.state.State",
]

UNCLONABLE_MODULES = ["_asyncio", "marimo._ast"]

EXECUTION_TYPES: dict[str, Type[Executor]] = {}


class MarimoMissingRefError(BaseException):
    def __init__(self, ref: str) -> None:
        self.ref = ref


def register_execution_type(
    key: str,
) -> Callable[[Type[Executor]], Type[Executor]]:
    def wrapper(cls: Type[Executor]) -> Type[Executor]:
        EXECUTION_TYPES[key] = cls
        return cls

    return wrapper


async def execute_cell_async(
    cell: CellImpl,
    glbls: dict[str, Any],
    execution_type: str = "relaxed",
) -> Any:
    return await EXECUTION_TYPES[execution_type].execute_cell_async(
        cell, glbls
    )


def execute_cell(
    cell: CellImpl, glbls: dict[str, Any], execution_type: str = "relaxed"
) -> Any:
    return EXECUTION_TYPES[execution_type].execute_cell(cell, glbls)


class Executor(ABC):
    @staticmethod
    @abstractmethod
    def execute_cell(cell: CellImpl, glbls: dict[str, Any]) -> Any:
        pass

    @staticmethod
    @abstractmethod
    async def execute_cell_async(cell: CellImpl, glbls: dict[str, Any]) -> Any:
        pass


@register_execution_type("relaxed")
class DefaultExecutor(Executor):
    @staticmethod
    async def execute_cell_async(cell: CellImpl, glbls: dict[str, Any]) -> Any:
        if cell.body is None:
            return None
        assert cell.last_expr is not None

        if _is_coroutine(cell.body):
            await eval(cell.body, glbls)
        else:
            exec(cell.body, glbls)

        if _is_coroutine(cell.last_expr):
            return await eval(cell.last_expr, glbls)
        else:
            return eval(cell.last_expr, glbls)

    @staticmethod
    def execute_cell(cell: CellImpl, glbls: dict[str, Any]) -> Any:
        if cell.body is None:
            return None
        assert cell.last_expr is not None
        exec(cell.body, glbls)
        return eval(cell.last_expr, glbls)


@register_execution_type("strict")
class StrictExecutor(Executor):
    @staticmethod
    async def execute_cell_async(cell: CellImpl, glbls: dict[str, Any]) -> Any:
        backup = StrictExecutor.sanitize_inputs(cell, glbls)
        try:
            response = await DefaultExecutor.execute_cell_async(cell, glbls)
        finally:
            # Restore globals from backup and backfill outputs
            StrictExecutor.update_outputs(cell, glbls, backup)
        return response

    @staticmethod
    def execute_cell(cell: CellImpl, glbls: dict[str, Any]) -> Any:
        backup = StrictExecutor.sanitize_inputs(cell, glbls)
        try:
            response = DefaultExecutor.execute_cell(cell, glbls)
        finally:
            StrictExecutor.update_outputs(cell, glbls, backup)
        return response

    @staticmethod
    def sanitize_inputs(
        cell: CellImpl, glbls: dict[str, Any]
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
        refs = cell.refs

        from asyncio import Future

        from marimo._plugins.ui._core.ui_element import UIElement
        from marimo._runtime.state import SetFunctor, State

        for ref in refs:
            if ref in glbls:
                if (
                    isinstance(
                        glbls[ref],
                        (State, SetFunctor, ZeroCopy, Future, UIElement),
                    )
                    or inspect.ismodule(glbls[ref])
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
                    raise NameError(
                        f"name `{ref}` is referenced before definition."
                    )
                raise MarimoMissingRefError(ref)

        # NOTE: Execution expects the globals dictionaty by memory reference,
        # so we need to clear it and update it with the sanitized locals,
        # returning a backup of the original globals for later restoration.
        # This must be performed at the end of the function to ensure valid
        # state.
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
            elif df in glbls:
                del glbls[df]

        from marimo._plugins.ui._core.ui_element import UIElement

        for df in lcls:
            if (
                df not in glbls
                and df.startswith(f"_cell_{cell.cell_id}_")
                and isinstance(lcls[df], UIElement)
            ):
                glbls[df] = lcls[df]


def is_instance_by_name(obj: object, name: str) -> bool:
    if not (hasattr(obj, "__module__") and hasattr(obj, "__class__")):
        return False
    obj_name = f"{obj.__module__}.{obj.__class__.__name__}"
    return obj_name == name


def is_unclonable_type(obj: object) -> bool:
    return any([is_instance_by_name(obj, name) for name in UNCLONABLE_TYPES])


def from_unclonable_module(obj: object) -> bool:
    return hasattr(obj, "__module__") and any(
        [obj.__module__.startswith(name) for name in UNCLONABLE_MODULES]
    )
