# Copyright 2026 Marimo. All rights reserved.
# Stub classes here conform to the ExecutionLifecycle / Executor
# Protocols, so they take `cell` / `glbls` even when the test body
# doesn't use them.
# ruff: noqa: ARG001, ARG002
"""Tests for the Evaluator + ExecutionLifecycle composition.

Covers setup chain order, Skip termination, teardown reverse order,
teardown visibility of body exceptions, teardown-wins semantics on
double raise, and KeyboardInterrupt propagation through teardown.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from marimo._runtime.exceptions import MarimoRuntimeException
from marimo._runtime.executor import (
    DefaultExecutor,
    Evaluator,
    EvaluatorConfig,
    ExecutionLifecycle,
    Skip,
    build_evaluator,
)
from marimo._runtime.runner.result import RunResult


class _Recorder:
    """Lifecycle that records setup/teardown calls into a shared log."""

    def __init__(
        self,
        log: list[str],
        tag: str,
        skip: Skip | None = None,
        setup_raises: BaseException | None = None,
        teardown_raises: BaseException | None = None,
    ) -> None:
        self.name = f"recorder-{tag}"
        self._log = log
        self._tag = tag
        self._skip = skip
        self._setup_raises = setup_raises
        self._teardown_raises = teardown_raises
        self.last_run_result: Any = None

    def setup(self, cell: Any, glbls: dict[str, Any]) -> Skip | None:
        self._log.append(f"setup:{self._tag}")
        if self._setup_raises is not None:
            raise self._setup_raises
        return self._skip

    def teardown(
        self, cell: Any, glbls: dict[str, Any], run_result: Any
    ) -> None:
        self._log.append(f"teardown:{self._tag}")
        self.last_run_result = run_result
        if self._teardown_raises is not None:
            raise self._teardown_raises


class _StubExecutor:
    """Executor that runs a caller-provided body, no exec/eval."""

    name = "stub"

    def __init__(self, body: Any) -> None:
        self._body = body

    def execute_cell(self, cell: Any, glbls: dict[str, Any]) -> Any:
        return self._body(cell, glbls)

    async def execute_cell_async(
        self, cell: Any, glbls: dict[str, Any]
    ) -> Any:
        result = self._body(cell, glbls)
        if asyncio.iscoroutine(result):
            return await result
        return result


@pytest.mark.asyncio
async def test_skip_terminates_setup_chain_but_runs_completed_teardowns() -> (
    None
):
    log: list[str] = []
    a = _Recorder(
        log, "A", skip=Skip(result=RunResult(output=42, exception=None))
    )
    b = _Recorder(log, "B")

    body_ran = [False]

    def body(cell: Any, glbls: dict[str, Any]) -> Any:
        body_ran[0] = True
        return "should-not-see-this"

    ev = Evaluator(executor=_StubExecutor(body), lifecycles=[a, b])
    result = await ev.evaluate(cell=None, glbls={})

    assert result.output == 42
    assert result.exception is None
    assert body_ran[0] is False
    # A setup ran, A teardown ran. B setup did NOT run, B teardown did
    # NOT run.
    assert log == ["setup:A", "teardown:A"]


@pytest.mark.asyncio
async def test_teardowns_fire_in_reverse_order_on_success() -> None:
    log: list[str] = []
    a = _Recorder(log, "A")
    b = _Recorder(log, "B")
    c = _Recorder(log, "C")

    ev = Evaluator(
        executor=_StubExecutor(lambda *_: "ok"),
        lifecycles=[a, b, c],
    )
    result = await ev.evaluate(cell=None, glbls={})

    assert result.output == "ok"
    assert result.exception is None
    assert log == [
        "setup:A",
        "setup:B",
        "setup:C",
        "teardown:C",
        "teardown:B",
        "teardown:A",
    ]


@pytest.mark.asyncio
async def test_teardown_sees_body_exception_via_run_result() -> None:
    log: list[str] = []
    a = _Recorder(log, "A")

    def boom(cell: Any, glbls: dict[str, Any]) -> Any:
        raise ValueError("body bomb")

    ev = Evaluator(executor=_StubExecutor(boom), lifecycles=[a])
    # The _StubExecutor doesn't wrap user exceptions; the body's
    # ValueError lands directly in result.exception, and the teardown
    # sees that same exception via run_result.
    result = await ev.evaluate(cell=None, glbls={})

    assert isinstance(result.exception, ValueError)
    assert str(result.exception) == "body bomb"
    assert a.last_run_result is not None
    assert isinstance(a.last_run_result.exception, ValueError)


@pytest.mark.asyncio
async def test_default_executor_wraps_user_exception_in_marimo_runtime() -> (
    None
):
    """DefaultExecutor turns user exceptions into MarimoRuntimeException
    with the user exception as __cause__. The teardown sees the wrapped
    form, and the returned RunResult carries it as its exception."""
    from marimo._ast.cell import CellImpl

    log: list[str] = []
    a = _Recorder(log, "A")

    body_src = "raise ValueError('user bomb')"

    class _FakeCell:
        cell_id = "0"
        body = compile(body_src, "<test>", "exec")
        last_expr = compile("None", "<test>", "eval")

        def is_coroutine(self) -> bool:
            return False

    del CellImpl  # silence unused-import
    ev = Evaluator(executor=DefaultExecutor(), lifecycles=[a])
    result = await ev.evaluate(_FakeCell(), {})  # type: ignore[arg-type]

    assert isinstance(result.exception, MarimoRuntimeException)
    assert isinstance(result.exception.__cause__, ValueError)
    assert a.last_run_result is not None
    # Teardown saw the wrapped exception, not the raw ValueError.
    assert isinstance(a.last_run_result.exception, MarimoRuntimeException)


@pytest.mark.asyncio
async def test_teardown_runs_for_completed_setups_when_later_setup_raises() -> (
    None
):
    log: list[str] = []
    a = _Recorder(log, "A")
    b = _Recorder(log, "B", setup_raises=RuntimeError("setup-B raised"))
    c = _Recorder(log, "C")  # never reached

    ev = Evaluator(
        executor=_StubExecutor(lambda *_: "ok"),
        lifecycles=[a, b, c],
    )
    result = await ev.evaluate(cell=None, glbls={})

    assert isinstance(result.exception, RuntimeError)
    assert str(result.exception) == "setup-B raised"
    # A.setup ran (completed), B.setup ran and raised, C.setup did not
    # run. Teardowns run only for lifecycles whose setup *completed*
    # without raising — so only A. B is not teardowned because its
    # state was never established.
    assert log == [
        "setup:A",
        "setup:B",
        "teardown:A",
    ]


@pytest.mark.asyncio
async def test_teardown_wins_on_double_raise() -> None:
    log: list[str] = []
    a = _Recorder(log, "A", teardown_raises=RuntimeError("teardown wins"))

    def body(cell: Any, glbls: dict[str, Any]) -> Any:
        raise ValueError("body loses")

    ev = Evaluator(executor=_StubExecutor(body), lifecycles=[a])
    result = await ev.evaluate(cell=None, glbls={})

    # Teardown exception replaces body exception in the final RunResult.
    assert isinstance(result.exception, RuntimeError)
    assert str(result.exception) == "teardown wins"


@pytest.mark.asyncio
async def test_keyboard_interrupt_captured_into_run_result() -> None:
    log: list[str] = []
    a = _Recorder(log, "A")

    def body(cell: Any, glbls: dict[str, Any]) -> Any:
        raise KeyboardInterrupt

    ev = Evaluator(executor=_StubExecutor(body), lifecycles=[a])
    result = await ev.evaluate(cell=None, glbls={})

    # Teardown ran (state still cleaned up) even though body raised
    # BaseException, and the interrupt is captured in the RunResult
    # rather than propagating out of evaluate().
    assert log == ["setup:A", "teardown:A"]
    assert isinstance(result.exception, KeyboardInterrupt)
    assert isinstance(a.last_run_result.exception, KeyboardInterrupt)


def test_strict_lifecycle_round_trip() -> None:
    """Globals restored to pre-state after StrictLifecycle setup +
    teardown."""
    from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

    class _FakeCell:
        cell_id = "c0"
        refs: set[str] = set()
        defs: set[str] = set()

    class _FakeGraph:
        def get_transitive_references(
            self, refs: set[str], predicate: Any
        ) -> set[str]:
            return set()

    lifecycle = StrictLifecycle(graph=_FakeGraph())  # type: ignore[arg-type]
    glbls: dict[str, Any] = {
        "x": 1,
        "y": [1, 2, 3],
        "__builtins__": __builtins__,
    }
    pre = {k: v for k, v in glbls.items()}

    skip = lifecycle.setup(_FakeCell(), glbls)  # type: ignore[arg-type]
    assert skip is None

    # During setup, glbls should be the sanitized scope (subset).
    assert "x" not in glbls  # No refs declared → x is not in scope.

    lifecycle.teardown(_FakeCell(), glbls, run_result=None)  # type: ignore[arg-type]

    # Globals restored — same values for unchanged keys.
    assert glbls["x"] == pre["x"]
    assert glbls["y"] == pre["y"]


def test_build_evaluator_from_config_instances() -> None:
    """EvaluatorConfig holds instances, not classes; build_evaluator is a
    one-liner."""
    executor = DefaultExecutor()
    config = EvaluatorConfig(executor=executor, lifecycles=[])
    evaluator = build_evaluator(config)

    assert isinstance(evaluator, Evaluator)
    assert evaluator.executor is executor
    assert evaluator.lifecycles == []


def test_execution_lifecycle_protocol_conformance() -> None:
    """A Protocol-conforming class without inheriting works as a
    lifecycle."""
    log: list[str] = []

    class _MyLifecycle:
        name = "mine"

        def setup(self, cell: Any, glbls: dict[str, Any]) -> Skip | None:
            log.append("setup")
            return None

        def teardown(
            self, cell: Any, glbls: dict[str, Any], run_result: Any
        ) -> None:
            log.append("teardown")

    # Static type check via assignment to a ExecutionLifecycle-typed
    # variable. If the Protocol is misshaped, mypy/pyright complains
    # here, not at runtime.
    lifecycle: ExecutionLifecycle = _MyLifecycle()
    assert lifecycle.name == "mine"
