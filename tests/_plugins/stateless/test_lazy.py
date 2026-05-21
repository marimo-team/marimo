# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import textwrap
from typing import Any

import pytest

import marimo as mo
from marimo._output.hypertext import patch_html_for_non_interactive_output
from marimo._runtime.context import get_context
from marimo._runtime.context.types import RuntimeContext
from marimo._runtime.functions import Function
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def get_only_function() -> Function[Any, Any]:
    context: RuntimeContext = get_context()
    assert len(context.function_registry.namespaces.values()) == 1
    first_namespace = next(iter(context.function_registry.namespaces.values()))
    assert len(first_namespace.functions) == 1
    return next(iter(first_namespace.functions.values()))


_LAZY_PROGRAMS = {
    "value": "lazy = mo.lazy(42)",
    "sync_callable": "lazy = mo.lazy(lambda: 42)",
    "async_callable": textwrap.dedent(
        """
        async def get_value():
            return 42
        lazy = mo.lazy(get_value)
        """
    ),
}


@pytest.mark.parametrize(
    "program", _LAZY_PROGRAMS.values(), ids=list(_LAZY_PROGRAMS)
)
async def test_lazy_load_function_resolves(
    k: Kernel, exec_req: ExecReqProvider, program: str
) -> None:
    await k.run([exec_req.get(f"import marimo as mo\n{program}")])
    fn = get_only_function()
    assert fn.name == "load"
    res = await fn({})
    assert res.html == "<span>42</span>"


async def test_lazy_is_lazy_in_interactive_context(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                textwrap.dedent(
                    """
                    import marimo as mo
                    calls = 0
                    def get_value():
                        global calls
                        calls += 1
                        return 42
                    lazy = mo.lazy(get_value)
                    """
                )
            ),
        ]
    )
    assert k.globals["calls"] == 0
    lazy_obj = k.globals["lazy"]
    assert "marimo-lazy" in lazy_obj.text
    assert "<span>42</span>" not in lazy_obj.text


@pytest.mark.parametrize(
    ("element_factory", "expected_html"),
    [
        pytest.param(lambda: 42, "<span>42</span>", id="value"),
        pytest.param(
            lambda: lambda: 42, "<span>42</span>", id="sync_callable"
        ),
        pytest.param(
            lambda: mo.md("# heading"), "<h1", id="ui_element_passthrough"
        ),
    ],
)
def test_lazy_resolves_eagerly_in_non_interactive_context(
    element_factory: Any, expected_html: str
) -> None:
    with patch_html_for_non_interactive_output():
        result = mo.lazy(element_factory())
    assert not isinstance(result, mo.lazy)
    assert expected_html in result.text


def test_lazy_sync_callable_is_invoked_exactly_once() -> None:
    calls = 0

    def get_value() -> int:
        nonlocal calls
        calls += 1
        return 42

    with patch_html_for_non_interactive_output():
        result = mo.lazy(get_value)
    assert calls == 1
    assert "<span>42</span>" in result.text


def _async_def() -> Any:
    async def get_value() -> int:
        return 42

    return get_value


def _coroutine_returning_lambda() -> Any:
    async def _inner() -> int:
        return 42

    return lambda: _inner()


def _raw_coroutine() -> Any:
    async def _inner() -> int:
        return 42

    return _inner()


@pytest.mark.parametrize(
    "make_element",
    [
        pytest.param(_async_def, id="async_callable"),
        pytest.param(_coroutine_returning_lambda, id="coroutine_return"),
        pytest.param(_raw_coroutine, id="raw_coroutine"),
    ],
)
def test_lazy_falls_back_to_widget_for_async_in_non_interactive_context(
    make_element: Any,
) -> None:
    with patch_html_for_non_interactive_output():
        result = mo.lazy(make_element())
    assert isinstance(result, mo.lazy)


def test_lazy_falls_back_to_widget_when_sync_callable_raises() -> None:
    def boom() -> int:
        raise RuntimeError("nope")

    with patch_html_for_non_interactive_output():
        result = mo.lazy(boom)
    assert isinstance(result, mo.lazy)
