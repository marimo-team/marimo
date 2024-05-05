from __future__ import annotations

import dataclasses

from marimo._runtime.functions import (
    Function,
    FunctionNamespace,
    FunctionRegistry,
)


@dataclasses.dataclass
class Args:
    value: int


def test_function_init() -> None:
    function = Function(
        name="test_function",
        arg_cls=Args,
        function=lambda x: x.value + 1,
    )

    assert function.name == "test_function"
    assert function.arg_cls == Args
    assert callable(function.function)
    assert function.cell_id is None


def test_function_call() -> None:
    function = Function(
        name="test_function",
        arg_cls=Args,
        function=lambda x: x.value + 1,
    )

    result = function({"value": 1})
    assert result == 2


async def test_function_async_call() -> None:
    async def async_function(x: Args) -> int:
        return x.value + 1

    function = Function(
        name="test_function",
        arg_cls=Args,
        function=async_function,
    )

    result = await function({"value": 1})
    assert result == 2


def test_function_namespace() -> None:
    namespace = FunctionNamespace(namespace="test_namespace")
    function = Function(
        name="test_function",
        arg_cls=Args,
        function=lambda x: x.value + 1,
    )

    namespace.add(function)
    assert namespace.get("test_function") == function
    assert namespace.get("non_existent_function") is None


def test_function_registry() -> None:
    registry = FunctionRegistry()
    namespace = "test_namespace"
    function = Function(
        name="test_function",
        arg_cls=Args,
        function=lambda x: x.value + 1,
    )

    registry.register(namespace, function)
    assert registry.get_function(namespace, "test_function") == function
    assert registry.get_function(namespace, "non_existent_function") is None
    assert (
        registry.get_function("non_existent_namespace", "test_function")
        is None
    )

    registry.delete(namespace)
    assert registry.get_function(namespace, "test_function") is None
