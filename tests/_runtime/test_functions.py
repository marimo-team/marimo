from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._runtime.commands import InvokeFunctionCommand
from marimo._runtime.context import get_context
from marimo._runtime.functions import (
    Function,
    FunctionNamespace,
    FunctionRegistry,
)
from marimo._types.ids import RequestId

if TYPE_CHECKING:
    import pytest

    from marimo._runtime.runtime import Kernel


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


def _invoke(namespace: str, function_name: str) -> InvokeFunctionCommand:
    return InvokeFunctionCommand(
        function_call_id=RequestId("call"),
        namespace=namespace,
        function_name=function_name,
        args={"value": 1},
    )


async def test_function_call_request_not_found(k: Kernel) -> None:
    status, _, found = await k.function_call_request(
        _invoke("unregistered-namespace", "missing")
    )
    assert found is False
    assert status.code == "error"
    assert status.title == "Function not found"


async def test_function_call_request_found_after_register(k: Kernel) -> None:
    namespace = "registered-namespace"
    get_context().function_registry.register(
        namespace,
        Function(name="echo", arg_cls=Args, function=lambda x: x.value),
    )

    _, _, found = await k.function_call_request(_invoke(namespace, "echo"))
    assert found is True


async def test_function_call_request_not_found_logs(
    k: Kernel, caplog: pytest.LogCaptureFixture
) -> None:
    logger = _loggers.marimo_logger()
    old_propagate = logger.propagate
    logger.propagate = True
    try:
        with caplog.at_level(logging.WARNING):
            await k.function_call_request(_invoke("missing-ns", "missing-fn"))
    finally:
        logger.propagate = old_propagate

    records = [
        record
        for record in caplog.records
        if "Function call not found" in record.getMessage()
    ]
    assert len(records) == 1
    message = records[0].getMessage()
    assert "namespace=missing-ns" in message
    assert "function=missing-fn" in message
    assert "namespace_registered=False" in message
    assert "child_contexts_searched=0" in message


async def test_function_call_request_found_does_not_log(
    k: Kernel, caplog: pytest.LogCaptureFixture
) -> None:
    namespace = "registered-namespace"
    get_context().function_registry.register(
        namespace,
        Function(name="echo", arg_cls=Args, function=lambda x: x.value),
    )

    logger = _loggers.marimo_logger()
    old_propagate = logger.propagate
    logger.propagate = True
    try:
        with caplog.at_level(logging.WARNING):
            await k.function_call_request(_invoke(namespace, "echo"))
    finally:
        logger.propagate = old_propagate

    assert not [
        record
        for record in caplog.records
        if "Function call not found" in record.getMessage()
    ]
