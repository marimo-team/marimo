# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._runtime.context import get_context
from marimo._runtime.context.types import RuntimeContext
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_routes_lazy(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                mo.routes(
                    {
                        "#/": lambda: 42,
                        "#/about": lambda: 43,
                        "#/contact": lambda: 44,
                        mo.routes.CATCH_ALL: lambda: 45,
                    }
                )
                """
            ),
        ]
    )

    context: RuntimeContext = get_context()
    # 4 functions, 1 for each route
    assert len(context.function_registry.namespaces.values()) == 4

    expected_results = [
        "<span>42</span>",
        "<span>43</span>",
        "<span>44</span>",
        "<span>45</span>",
    ]

    for i, expected in enumerate(context.function_registry.namespaces):
        function = next(
            iter(
                context.function_registry.namespaces[
                    expected
                ].functions.values()
            )
        )
        res = await function({})
        assert res.html == expected_results[i]
        assert function.name == "load"


async def test_routes_non_lazy(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                routes = mo.routes(
                    {
                        "#/": 42,
                        mo.routes.CATCH_ALL: 45,
                    }
                )
                """
            ),
        ]
    )

    context: RuntimeContext = get_context()
    # No functions, all routes are non-lazy
    assert len(context.function_registry.namespaces.values()) == 0

    routes = k.globals["routes"]
    children = "<span>42</span><span>45</span>"
    assert children in routes.text
    assert (
        "data-routes='[&quot;#/&quot;,&quot;{/*path}&quot;]'" in routes.text
    )
