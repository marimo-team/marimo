# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import textwrap
from typing import Any

import pytest

import marimo as mo
from marimo._messaging.notification import CellNotification
from marimo._output.hypertext import patch_html_for_non_interactive_output
from marimo._runtime.commands import InvokeFunctionCommand
from marimo._runtime.context import get_context
from marimo._runtime.context.types import RuntimeContext
from marimo._runtime.functions import Function
from marimo._runtime.runtime import Kernel
from marimo._types.ids import RequestId
from tests.conftest import ExecReqProvider


def get_only_function() -> Function[Any, Any]:
    context: RuntimeContext = get_context()
    assert len(context.function_registry.namespaces.values()) == 1
    first_namespace = next(iter(context.function_registry.namespaces.values()))
    assert len(first_namespace.functions) == 1
    return next(iter(first_namespace.functions.values()))


async def _invoke_only_function(k: Kernel) -> tuple[Any, list[str]]:
    """Invoke the sole registered function via the full RPC path.

    Going through `function_call_request` (rather than calling the function
    directly) installs the owning cell's execution context, which is what
    makes imperative `mo.output` calls inside a deferred render observable.
    Returns the payload and the string data of every cell output broadcast
    to the owning cell during the call.
    """
    context: RuntimeContext = get_context()
    namespace = next(iter(context.function_registry.namespaces))
    fn = get_only_function()
    n_before = len(k.stream.messages)  # type: ignore[attr-defined]
    _status, payload, _found = await k.function_call_request(
        InvokeFunctionCommand(
            function_call_id=RequestId("call"),
            namespace=namespace,
            function_name=fn.name,
            args={},
        )
    )
    new_ops = k.stream.operations[n_before:]  # type: ignore[attr-defined]
    cell_output_data = [
        str(op.output.data)
        for op in new_ops
        if isinstance(op, CellNotification) and op.output is not None
    ]
    return payload, cell_output_data


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


async def test_lazy_return_value_takes_precedence_over_append(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    # Regression test for #9540: a deferred render that both appends to the
    # output and returns a value should show the returned value.
    await k.run(
        [
            exec_req.get(
                textwrap.dedent(
                    """
                    import marimo as mo
                    def _():
                        mo.output.append("appended")
                        return mo.md("returned")
                    lazy = mo.lazy(_)
                    """
                )
            ),
        ]
    )
    payload, cell_output_data = await _invoke_only_function(k)
    # The lazy widget shows the returned value, not the appended one.
    assert "returned" in payload.html
    assert "appended" not in payload.html
    # The imperative append must not clobber the owning cell's output.
    for data in cell_output_data:
        assert "appended" not in data


async def test_lazy_falls_back_to_appended_output_when_no_return(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    # When the deferred callable returns nothing, its imperative output is
    # rendered inside the lazy widget rather than lost.
    await k.run(
        [
            exec_req.get(
                textwrap.dedent(
                    """
                    import marimo as mo
                    def _():
                        mo.output.append("appended")
                    lazy = mo.lazy(_)
                    """
                )
            ),
        ]
    )
    payload, cell_output_data = await _invoke_only_function(k)
    assert "appended" in payload.html
    # Still no leak into the owning cell's output.
    for data in cell_output_data:
        assert "appended" not in data
