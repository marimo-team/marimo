# Copyright 2024 Marimo. All rights reserved.
"""Functions associated with a graph."""

from __future__ import annotations

import dataclasses
from typing import Any, Callable, Coroutine, Generic, Type, TypeVar

from marimo._ast.cell import CellId_t
from marimo._utils.parse_dataclass import parse_raw

S = TypeVar("S")
T = TypeVar("T")


@dataclasses.dataclass
class EmptyArgs:
    """Utility type for functions that take no arguments."""

    ...


@dataclasses.dataclass
class Function(Generic[S, T]):
    name: str
    arg_cls: Type[S]
    function: Callable[[S], T] | Callable[[S], Coroutine[Any, Any, T]]
    cell_id: CellId_t | None

    def __init__(
        self,
        name: str,
        arg_cls: Type[S],
        function: Callable[[S], T],
    ) -> None:
        from marimo._runtime.context import (
            ContextNotInitializedError,
            get_context,
        )

        self.name = name
        self.arg_cls = arg_cls
        self.function = function

        try:
            ctx = get_context()
        except ContextNotInitializedError:
            ctx = None

        if ctx is not None and ctx.execution_context is not None:
            self.cell_id = ctx.execution_context.cell_id
        else:
            self.cell_id = None

    def __call__(self, args: dict[Any, Any]) -> T | Coroutine[Any, Any, T]:
        return self.function(parse_raw(args, self.arg_cls))


@dataclasses.dataclass
class FunctionNamespace:
    namespace: str
    functions: dict[str, Function[Any, Any]] = dataclasses.field(
        default_factory=dict
    )

    def add(self, function: Function[Any, Any]) -> None:
        self.functions[function.name] = function

    def get(self, name: str) -> Function[Any, Any] | None:
        if name in self.functions:
            return self.functions[name]
        return None


class FunctionRegistry:
    def __init__(self) -> None:
        self.namespaces: dict[str, FunctionNamespace] = {}

    def register(self, namespace: str, function: Function[Any, Any]) -> None:
        if namespace not in self.namespaces:
            self.namespaces[namespace] = FunctionNamespace(namespace=namespace)
        self.namespaces[namespace].add(function)

    def get_function(
        self, namespace: str, function_name: str
    ) -> Function[Any, Any] | None:
        if namespace in self.namespaces:
            return self.namespaces[namespace].get(function_name)
        return None

    def delete(self, namespace: str) -> None:
        if namespace in self.namespaces:
            del self.namespaces[namespace]
