# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import queue as _queue
import threading
from collections import deque
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from marimo._runtime.commands import (
    BatchableCommand,
    CancelRunCommand,
    CodeCompletionCommand,
    CommandMessage,
    ExecuteCellsCommand,
    ModelCommand,
    SetBreakpointsCommand,
    StopKernelCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.kernel_lifecycle import (
    asyncio_queue_reader,
    collapse_out_of_band,
    drain_pending,
    drain_stale,
    listen_messages,
    make_control_enqueuer,
    threaded_queue_reader,
)
from marimo._types.ids import (
    CellId_t,
    RequestId,
    UIElementId,
    WidgetModelId,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


class FakeKernel:
    """Records the commands the control loop dispatches."""

    def __init__(self) -> None:
        self.handle_message = AsyncMock()


@pytest.fixture
def kernel() -> FakeKernel:
    return FakeKernel()


@pytest.fixture
def control() -> asyncio.Queue[CommandMessage]:
    return asyncio.Queue()


@pytest.fixture
def ui() -> asyncio.Queue[BatchableCommand]:
    return asyncio.Queue()


def _execute(cell_id: str = "c1") -> ExecuteCellsCommand:
    return ExecuteCellsCommand(cell_ids=[CellId_t(cell_id)], codes=["x = 1"])


def _ui_update(
    elem_id: str = "u1", value: Any = None
) -> UpdateUIElementCommand:
    return UpdateUIElementCommand(
        object_ids=[UIElementId(elem_id)], values=[value]
    )


async def test_threaded_queue_reader_offloads_blocking_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    q: _queue.Queue[CommandMessage] = _queue.Queue()
    command = StopKernelCommand()
    q.put(command)

    event_loop_thread = threading.current_thread()
    reader_thread: threading.Thread | None = None
    original_get = q.get

    def tracked_get() -> CommandMessage:
        nonlocal reader_thread
        reader_thread = threading.current_thread()
        return original_get()

    monkeypatch.setattr(q, "get", tracked_get)

    assert await threaded_queue_reader(q) is command
    assert reader_thread is not None
    assert reader_thread is not event_loop_thread


async def test_listen_messages_exits_on_stop_command(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    cmd = _execute()
    control.put_nowait(cmd)
    control.put_nowait(StopKernelCommand())
    # A request enqueued *after* StopKernel must not be dispatched.
    control.put_nowait(_execute("after-stop"))

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    assert kernel.handle_message.await_count == 1
    assert kernel.handle_message.await_args_list[-1].args == (cmd,)


async def test_listen_messages_skips_none_requests(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    cmd = _execute()
    reads = iter([None, cmd, StopKernelCommand()])

    async def reader(_queue: object) -> CommandMessage | None:
        return next(reads)

    await listen_messages(kernel, control, ui, reader)

    assert kernel.handle_message.await_count == 1
    assert kernel.handle_message.await_args_list[-1].args == (cmd,)


async def test_listen_messages_swallows_handle_message_exception_non_ui(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    kernel.handle_message.side_effect = [RuntimeError("boom"), None]
    control.put_nowait(_execute("first"))
    control.put_nowait(_execute("second"))
    control.put_nowait(StopKernelCommand())

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    # Second dispatch proves the loop survived the first raise.
    assert kernel.handle_message.await_count == 2


async def test_listen_messages_swallows_handle_message_exception_ui_branch(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    """Regression test: the UI-merge branch used to let `handle_message`
    exceptions propagate while the non-UI branch caught them."""
    kernel.handle_message.side_effect = [RuntimeError("boom"), None]
    ui_cmd = _ui_update()
    control.put_nowait(ui_cmd)
    ui.put_nowait(ui_cmd)
    control.put_nowait(_execute("after-ui"))
    control.put_nowait(StopKernelCommand())

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    assert kernel.handle_message.await_count == 2


def _run(run_id: str) -> ExecuteCellsCommand:
    return ExecuteCellsCommand(
        cell_ids=[CellId_t("c1")], codes=["x = 1"], run_id=run_id
    )


async def test_listen_messages_cancels_a_run_still_in_the_queue(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    """A cancellation enqueued while an earlier run executes takes the
    place of the run it names, which the kernel never sees."""

    async def arrive_during_first(request: CommandMessage) -> None:
        if getattr(request, "run_id", None) == "first":
            control.put_nowait(_run("second"))
            control.put_nowait(_run("third"))
            control.put_nowait(CancelRunCommand(run_id="second"))
            control.put_nowait(StopKernelCommand())

    kernel.handle_message.side_effect = arrive_during_first
    control.put_nowait(_run("first"))

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    dispatched = [
        call.args[0] for call in kernel.handle_message.await_args_list
    ]
    assert [type(r).__name__ for r in dispatched] == [
        "ExecuteCellsCommand",
        "CancelRunCommand",
        "ExecuteCellsCommand",
    ]
    assert [r.run_id for r in dispatched] == ["first", "second", "third"]


async def test_listen_messages_drops_a_cancellation_whose_run_already_left(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    control.put_nowait(CancelRunCommand(run_id="gone"))
    control.put_nowait(_run("later"))
    control.put_nowait(StopKernelCommand())

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    assert kernel.handle_message.await_count == 1
    assert kernel.handle_message.await_args_list[-1].args[0].run_id == "later"


def test_drain_pending_stops_at_a_broken_queue() -> None:
    class Broken:
        def get_nowait(self) -> CommandMessage:
            raise OSError("queue closed")

    pending: deque[CommandMessage] = deque([_run("first")])
    drain_pending(Broken(), pending)
    assert [r.run_id for r in pending] == ["first"]  # type: ignore[union-attr]


async def test_listen_messages_exits_when_reader_raises(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    async def failing_reader(_queue: object) -> CommandMessage:
        raise OSError("queue closed")

    await listen_messages(kernel, control, ui, failing_reader)

    kernel.handle_message.assert_not_called()


async def test_listen_messages_survives_interrupted_read(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    """A SIGINT-aborted queue read (EINTR) must not stop the control
    loop."""
    cmd = _execute()
    reads: Iterator[CommandMessage | BaseException] = iter(
        [
            InterruptedError(4, "Interrupted function call"),
            cmd,
            StopKernelCommand(),
        ]
    )

    async def interrupted_reader(_queue: object) -> CommandMessage:
        result = next(reads)
        if isinstance(result, BaseException):
            raise result
        return result

    await listen_messages(kernel, control, ui, interrupted_reader)

    # The dispatch after the EINTR proves the loop kept reading.
    assert kernel.handle_message.await_count == 1
    assert kernel.handle_message.await_args_list[-1].args == (cmd,)


async def test_listen_messages_merges_ui_updates(
    kernel: FakeKernel,
    control: asyncio.Queue[CommandMessage],
    ui: asyncio.Queue[BatchableCommand],
) -> None:
    """Contiguous UI updates against the same element collapse to one dispatch."""
    first = _ui_update("u", 1)
    second = _ui_update("u", 2)
    # Enqueue both on control + ui (matches what _enqueue_control_request does).
    control.put_nowait(first)
    ui.put_nowait(first)
    control.put_nowait(second)
    ui.put_nowait(second)
    control.put_nowait(StopKernelCommand())

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    # Both UI updates merge into a single batched dispatch.
    assert kernel.handle_message.await_count == 1
    dispatched = kernel.handle_message.await_args_list[-1].args[0]
    assert isinstance(dispatched, UpdateUIElementCommand)
    assert dispatched.values == [2]


@pytest.mark.parametrize(
    "queue_factory",
    [asyncio.Queue, _queue.Queue],
    ids=["asyncio", "threading"],
)
def test_drain_stale_returns_latest_when_queue_empty(
    queue_factory: Any,
) -> None:
    q = queue_factory()
    latest = _execute("only")
    assert drain_stale(q, latest=latest) is latest


@pytest.mark.parametrize(
    "queue_factory",
    [asyncio.Queue, _queue.Queue],
    ids=["asyncio", "threading"],
)
def test_drain_stale_returns_newest_pending(queue_factory: Any) -> None:
    q = queue_factory()
    initial = _execute("initial")
    newer = _execute("newer")
    newest = _execute("newest")
    q.put_nowait(newer)
    q.put_nowait(newest)

    assert drain_stale(q, latest=initial) is newest
    # Drained: nothing else remains.
    assert q.empty()


@pytest.mark.parametrize(
    "queue_factory",
    [asyncio.Queue, _queue.Queue],
    ids=["asyncio", "threading"],
)
def test_collapse_out_of_band_returns_first_when_empty(
    queue_factory: Any,
) -> None:
    q = queue_factory()
    first = CodeCompletionCommand(
        id=RequestId("r1"), document="x.", cell_id=CellId_t("c1")
    )
    assert collapse_out_of_band(q, first=first) == [first]


@pytest.mark.parametrize(
    "queue_factory",
    [asyncio.Queue, _queue.Queue],
    ids=["asyncio", "threading"],
)
def test_collapse_out_of_band_keeps_latest_per_type(
    queue_factory: Any,
) -> None:
    q = queue_factory()
    completion_old = CodeCompletionCommand(
        id=RequestId("r1"), document="x.", cell_id=CellId_t("c1")
    )
    breakpoints = SetBreakpointsCommand(breakpoints={CellId_t("c1"): [1]})
    completion_new = CodeCompletionCommand(
        id=RequestId("r2"), document="y.", cell_id=CellId_t("c1")
    )
    q.put_nowait(breakpoints)
    q.put_nowait(completion_new)

    result = collapse_out_of_band(q, first=completion_old)

    # One command per type, latest wins, in first-seen order.
    assert result == [completion_new, breakpoints]
    assert q.empty()


def test_make_control_enqueuer_routes_plain_command_to_control_only() -> None:
    control: asyncio.Queue[CommandMessage] = asyncio.Queue()
    ui: asyncio.Queue[BatchableCommand] = asyncio.Queue()
    enqueue = make_control_enqueuer(control, ui)

    cmd = _execute()
    enqueue(cmd)

    assert control.get_nowait() is cmd
    assert ui.empty()


def test_make_control_enqueuer_mirrors_ui_element_command() -> None:
    control: asyncio.Queue[CommandMessage] = asyncio.Queue()
    ui: asyncio.Queue[BatchableCommand] = asyncio.Queue()
    enqueue = make_control_enqueuer(control, ui)

    cmd = _ui_update("u", 1)
    enqueue(cmd)

    assert control.get_nowait() is cmd
    assert ui.get_nowait() is cmd


def test_make_control_enqueuer_mirrors_model_command() -> None:
    from marimo._runtime.commands import ModelUpdateMessage

    control: asyncio.Queue[CommandMessage] = asyncio.Queue()
    ui: asyncio.Queue[BatchableCommand] = asyncio.Queue()
    enqueue = make_control_enqueuer(control, ui)

    cmd = ModelCommand(
        model_id=WidgetModelId("m1"),
        message=ModelUpdateMessage(state={"x": 1}, buffer_paths=[]),
        buffers=[],
    )
    enqueue(cmd)

    assert control.get_nowait() is cmd
    assert ui.get_nowait() is cmd
