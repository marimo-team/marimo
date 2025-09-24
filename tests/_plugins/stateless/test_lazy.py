# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._runtime.context import get_context
from marimo._runtime.context.types import RuntimeContext
from marimo._runtime.functions import Function
from marimo._runtime.runtime.kernel import Kernel
from tests.conftest import ExecReqProvider


def get_only_function() -> Function[Any, Any]:
    context: RuntimeContext = get_context()
    assert len(context.function_registry.namespaces.values()) == 1
    first_namespace = next(iter(context.function_registry.namespaces.values()))
    assert len(first_namespace.functions) == 1
    return next(iter(first_namespace.functions.values()))


async def test_lazy(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                lazy = mo.lazy(42)
                """
            ),
        ]
    )
    first_function = get_only_function()
    assert first_function.name == "load"
    res = await first_function({})
    assert res.html == "<span>42</span>"


async def test_lazy_function(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                lazy = mo.lazy(lambda: 42)
                """
            ),
        ]
    )
    first_function = get_only_function()
    assert first_function.name == "load"
    res = await first_function({})
    assert res.html == "<span>42</span>"


async def test_lazy_async_function(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                async def get_value():
                    return 42
                lazy = mo.lazy(get_value)
                """
            ),
        ]
    )
    first_function = get_only_function()
    assert first_function.name == "load"
    res = await first_function({})
    assert res.html == "<span>42</span>"
