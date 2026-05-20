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
    ExecutionLifecycle,
    Skip,
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


async def test_skip_result_preserves_accumulated_output() -> None:
    """`Skip(result=RunResult(...))` threads the entire RunResult
    through teardown — `output`, `exception`, and
    `accumulated_output` all survive, including any future fields
    added to `RunResult`."""
    log: list[str] = []
    skip_result = RunResult(
        output="cached", exception=None, accumulated_output="streamed"
    )
    a = _Recorder(log, "A", skip=Skip(result=skip_result))

    ev = Evaluator(executor=_StubExecutor(lambda *_: "unused"), lifecycles=[a])
    result = await ev.evaluate(cell=None, glbls={})

    assert result.output == "cached"
    assert result.accumulated_output == "streamed"
    assert result.exception is None
    # Teardown saw the same RunResult that came back out.
    assert a.last_run_result is result


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


def _cause_traceback_filenames(exc: BaseException) -> list[str]:
    cause = exc.__cause__
    assert cause is not None
    tb = cause.__traceback__
    files: list[str] = []
    while tb is not None:
        files.append(tb.tb_frame.f_code.co_filename)
        tb = tb.tb_next
    return files


def test_default_executor_strips_own_frame_from_cause_sync() -> None:
    """``DefaultExecutor.execute_cell`` must not leave its own frame on
    the cause's ``__traceback__`` — user-facing tracebacks should begin
    at user code (the compiled ``<test>`` source)."""

    class _FakeCell:
        cell_id = "0"
        body = compile("raise ValueError('user bomb')", "<test>", "exec")
        last_expr = compile("None", "<test>", "eval")

    with pytest.raises(MarimoRuntimeException) as exc_info:
        DefaultExecutor().execute_cell(_FakeCell(), {})  # type: ignore[arg-type]

    files = _cause_traceback_filenames(exc_info.value)
    assert files, "cause traceback unexpectedly empty"
    assert not any("executor/executor.py" in f for f in files), files
    assert files[0] == "<test>"


async def test_default_executor_strips_own_frame_from_cause_async() -> None:
    """Same as the sync variant, for ``execute_cell_async``."""

    class _FakeCell:
        cell_id = "0"
        body = compile("raise ValueError('user bomb')", "<test>", "exec")
        last_expr = compile("None", "<test>", "eval")

    with pytest.raises(MarimoRuntimeException) as exc_info:
        await DefaultExecutor().execute_cell_async(_FakeCell(), {})  # type: ignore[arg-type]

    files = _cause_traceback_filenames(exc_info.value)
    assert files, "cause traceback unexpectedly empty"
    assert not any("executor/executor.py" in f for f in files), files
    assert files[0] == "<test>"


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


class _StrictGraph:
    """``_FakeGraph`` for ``StrictLifecycle`` setup-path tests.

    ``transitive_refs`` controls what ``get_transitive_references`` returns
    so the test can drive ``setup`` past sanitization into the
    error-construction branch. ``defining_cells`` maps refs to defining
    cell IDs; refs absent from the map raise ``KeyError`` to exercise
    the ``unmangle_local`` fallback.
    """

    def __init__(
        self,
        transitive_refs: set[str],
        defining_cells: dict[str, list[str]] | None = None,
    ) -> None:
        self._transitive_refs = transitive_refs
        self._defining_cells = defining_cells or {}

    def get_transitive_references(
        self, refs: set[str], predicate: Any
    ) -> set[str]:
        return set(self._transitive_refs)

    def get_defining_cells(self, ref: str) -> list[str]:
        return self._defining_cells[ref]


class _StrictCell:
    def __init__(self, refs: set[str], defs: set[str] | None = None) -> None:
        self.cell_id = "c0"
        self.refs = refs
        self.defs = defs or set()


def test_strict_setup_skip_on_undefined_ref() -> None:
    """Unresolved ref → ``Skip(result=RunResult(output=err, exception=err))``
    where ``err`` is a ``MarimoStrictExecutionError`` with no blamed cell
    (graph has no defining cell and the ref is not a private var)."""
    from marimo._messaging.errors import MarimoStrictExecutionError
    from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

    lifecycle = StrictLifecycle(
        graph=_StrictGraph(transitive_refs={"x"})  # type: ignore[arg-type]
    )
    glbls: dict[str, Any] = {"__builtins__": {}}

    skip = lifecycle.setup(_StrictCell(refs={"x"}), glbls)  # type: ignore[arg-type]

    assert skip is not None
    assert skip.result is not None
    err = skip.result.exception
    assert isinstance(err, MarimoStrictExecutionError)
    assert err.ref == "x"
    assert err.blamed_cell is None
    assert skip.result.output is err


def test_strict_setup_skip_on_ref_before_def() -> None:
    """Ref appears in the cell's own ``defs`` → ref-before-def branch."""
    from marimo._messaging.errors import MarimoStrictExecutionError
    from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

    lifecycle = StrictLifecycle(
        graph=_StrictGraph(transitive_refs={"x"})  # type: ignore[arg-type]
    )
    glbls: dict[str, Any] = {"__builtins__": {}}

    skip = lifecycle.setup(
        _StrictCell(refs={"x"}, defs={"x"}),  # type: ignore[arg-type]
        glbls,
    )

    assert skip is not None
    assert skip.result is not None
    err = skip.result.exception
    assert isinstance(err, MarimoStrictExecutionError)
    assert err.ref == "x"
    assert err.blamed_cell is None


def test_strict_setup_skip_resolves_blamed_cell_via_graph() -> None:
    """``get_defining_cells`` returns the owning cell → blamed_cell."""
    from marimo._messaging.errors import MarimoStrictExecutionError
    from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

    lifecycle = StrictLifecycle(
        graph=_StrictGraph(  # type: ignore[arg-type]
            transitive_refs={"x"},
            defining_cells={"x": ["other"]},
        )
    )
    glbls: dict[str, Any] = {"__builtins__": {}}

    skip = lifecycle.setup(_StrictCell(refs={"x"}), glbls)  # type: ignore[arg-type]

    assert skip is not None
    assert skip.result is not None
    err = skip.result.exception
    assert isinstance(err, MarimoStrictExecutionError)
    assert err.blamed_cell == "other"


def test_strict_setup_skip_falls_back_to_private_var_owner() -> None:
    """``KeyError`` from the graph → ``unmangle_local`` resolves the
    owning cell for mangled private vars."""
    from marimo._messaging.errors import MarimoStrictExecutionError
    from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

    # ``_cell_ZZZ_priv`` unmangles to (name="_priv", cell="ZZZ").
    private_ref = "_cell_ZZZ_priv"
    lifecycle = StrictLifecycle(
        graph=_StrictGraph(  # type: ignore[arg-type]
            transitive_refs={private_ref},
        )
    )
    glbls: dict[str, Any] = {"__builtins__": {}}

    skip = lifecycle.setup(
        _StrictCell(refs={private_ref}),  # type: ignore[arg-type]
        glbls,
    )

    assert skip is not None
    assert skip.result is not None
    err = skip.result.exception
    assert isinstance(err, MarimoStrictExecutionError)
    assert err.blamed_cell == "ZZZ"


def test_strict_setup_skip_does_not_mutate_globals_or_stash_backup() -> None:
    """The Skip early-return must happen before globals are cleared and
    before the backup is stashed. ``teardown`` must then be a no-op."""
    from marimo._runtime.executor.lifecycles.strict import StrictLifecycle

    lifecycle = StrictLifecycle(
        graph=_StrictGraph(transitive_refs={"x"})  # type: ignore[arg-type]
    )
    glbls: dict[str, Any] = {
        "preserve_me": 42,
        "__builtins__": {},
    }
    pre = dict(glbls)

    skip = lifecycle.setup(_StrictCell(refs={"x"}), glbls)  # type: ignore[arg-type]
    assert skip is not None
    assert glbls == pre, "Skip path must not mutate globals"
    assert lifecycle._backups == {}, "Skip path must not stash a backup"

    lifecycle.teardown(_StrictCell(refs={"x"}), glbls, skip.result)  # type: ignore[arg-type]
    assert glbls == pre, "teardown after Skip must be a no-op"


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


# --- Surface 4: _cancel_on_sigint + evaluate_interruptible ------------------


def _async_body(src: str) -> Any:
    """Compile ``src`` with top-level-await support; returns a code object
    whose ``co_flags`` carry ``CO_COROUTINE`` so ``_is_coroutine`` is True."""
    import ast

    return compile(src, "<test>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


async def test_cancel_on_sigint_installs_and_restores_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_cancel_on_sigint`` swaps in its own handler on enter and
    restores the previously-installed one on exit."""
    import signal

    from marimo._runtime.executor.evaluator import _cancel_on_sigint

    def prior(signum: int, frame: Any) -> None:
        del signum, frame

    signal_calls: list[tuple[int, Any]] = []

    def fake_signal(signum: int, handler: Any) -> Any:
        signal_calls.append((signum, handler))
        return prior

    monkeypatch.setattr(signal, "signal", fake_signal)
    monkeypatch.setattr(signal, "getsignal", lambda _signum: prior)

    fut: asyncio.Future[Any] = asyncio.Future()
    with _cancel_on_sigint(fut):
        # On enter: a new handler installed (not the prior).
        assert signal_calls, "no signal.signal call recorded on enter"
        assert signal_calls[0][0] == signal.SIGINT
        assert signal_calls[0][1] is not prior

    # On exit: prior handler restored as the last call.
    assert signal_calls[-1] == (signal.SIGINT, prior)


async def test_cancel_on_sigint_handler_cancels_future_and_chains_prior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The installed handler must cancel the wrapped future and invoke
    the previously-installed handler for its side effects."""
    import signal

    from marimo._runtime.executor.evaluator import _cancel_on_sigint

    prior_calls: list[tuple[int, Any]] = []

    def prior(signum: int, frame: Any) -> None:
        prior_calls.append((signum, frame))

    captured: list[Any] = []

    def fake_signal(signum: int, handler: Any) -> Any:
        captured.append(handler)
        return prior

    monkeypatch.setattr(signal, "signal", fake_signal)
    monkeypatch.setattr(signal, "getsignal", lambda _signum: prior)

    fut: asyncio.Future[Any] = asyncio.Future()
    with _cancel_on_sigint(fut):
        marimo_handler = captured[0]
        marimo_handler(signal.SIGINT, None)
        # Cancellation propagates through done-callbacks asynchronously;
        # yield to the loop so they fire.
        await asyncio.sleep(0)

        assert fut.cancelled()
        assert prior_calls == [(signal.SIGINT, None)]


async def test_cancel_on_sigint_swallows_marimo_interrupt_from_prior_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prior handler raising ``MarimoInterrupt`` must not escape — the
    kernel's sync-mode raise is irrelevant for async cells, where the
    halt comes from cancelling the future."""
    import signal

    from marimo._runtime.control_flow import MarimoInterrupt
    from marimo._runtime.executor.evaluator import _cancel_on_sigint

    def prior(signum: int, frame: Any) -> None:
        raise MarimoInterrupt

    captured: list[Any] = []

    def fake_signal(signum: int, handler: Any) -> Any:
        captured.append(handler)
        return prior

    monkeypatch.setattr(signal, "signal", fake_signal)
    monkeypatch.setattr(signal, "getsignal", lambda _signum: prior)

    fut: asyncio.Future[Any] = asyncio.Future()
    with _cancel_on_sigint(fut):
        marimo_handler = captured[0]
        # No exception escapes — the wrapper catches MarimoInterrupt
        # from the prior handler.
        marimo_handler(signal.SIGINT, None)
        await asyncio.sleep(0)
        assert fut.cancelled()


async def test_executor_async_cancellation_propagates_unwrapped() -> None:
    """``asyncio.CancelledError`` must propagate unwrapped through
    ``DefaultExecutor.execute_cell_async`` — wrapping it as
    ``MarimoRuntimeException`` would defeat the runner's bare-
    ``CancelledError`` branch and prevent ``runner.interrupted`` from
    flipping on async SIGINT."""

    class _AsyncCell:
        cell_id = "0"
        body = _async_body("import asyncio\nawait asyncio.sleep(100)")
        last_expr = compile("None", "<test>", "eval")

        def is_coroutine(self) -> bool:
            return True

    task = asyncio.create_task(
        DefaultExecutor().execute_cell_async(_AsyncCell(), {})  # type: ignore[arg-type]
    )
    # Yield so the task enters the awaited sleep before we cancel.
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


async def test_evaluate_interruptible_no_op_for_sync_cell() -> None:
    """Sync cells: ``evaluate_interruptible`` returns the same shape as a
    direct ``evaluate()`` call. The SIGINT-handler wrap is for async only."""

    class _SyncCell:
        cell_id = "0"
        body = compile("x = 1", "<test>", "exec")
        last_expr = compile("x", "<test>", "eval")

        def is_coroutine(self) -> bool:
            return False

    ev = Evaluator(executor=DefaultExecutor(), lifecycles=[])

    sync_glbls: dict[str, Any] = {}
    interruptible_glbls: dict[str, Any] = {}

    direct = await ev.evaluate(_SyncCell(), sync_glbls)  # type: ignore[arg-type]
    interruptible = await ev.evaluate_interruptible(
        _SyncCell(),  # type: ignore[arg-type]
        interruptible_glbls,
    )

    assert direct.output == interruptible.output == 1
    assert direct.exception is None
    assert interruptible.exception is None
    assert direct.accumulated_output == interruptible.accumulated_output
