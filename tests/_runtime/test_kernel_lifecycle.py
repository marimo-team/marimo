# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from marimo._runtime.commands import (
    ExecuteCellsCommand,
    StopKernelCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.kernel_lifecycle import (
    asyncio_queue_reader,
    listen_messages,
)
from marimo._types.ids import CellId_t, UIElementId


@pytest.fixture
def kernel() -> Any:
    k = MagicMock()
    k.handle_message = AsyncMock()
    return k


@pytest.fixture
def control() -> asyncio.Queue[Any]:
    return asyncio.Queue()


@pytest.fixture
def ui() -> asyncio.Queue[Any]:
    return asyncio.Queue()


def _execute(cell_id: str = "c1") -> ExecuteCellsCommand:
    return ExecuteCellsCommand(cell_ids=[CellId_t(cell_id)], codes=["x = 1"])


def _ui_update(
    elem_id: str = "u1", value: Any = None
) -> UpdateUIElementCommand:
    return UpdateUIElementCommand(
        object_ids=[UIElementId(elem_id)], values=[value]
    )


async def test_listen_messages_exits_on_stop_command(
    kernel: Any,
    control: asyncio.Queue[Any],
    ui: asyncio.Queue[Any],
) -> None:
    cmd = _execute()
    control.put_nowait(cmd)
    control.put_nowait(StopKernelCommand())
    # A request enqueued *after* StopKernel must not be dispatched.
    control.put_nowait(_execute("after-stop"))

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    assert kernel.handle_message.await_count == 1
    assert kernel.handle_message.await_args.args == (cmd,)


async def test_listen_messages_skips_none_requests(
    kernel: Any,
    control: asyncio.Queue[Any],
    ui: asyncio.Queue[Any],
) -> None:
    control.put_nowait(None)
    cmd = _execute()
    control.put_nowait(cmd)
    control.put_nowait(StopKernelCommand())

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    assert kernel.handle_message.await_count == 1
    assert kernel.handle_message.await_args.args == (cmd,)


async def test_listen_messages_swallows_handle_message_exception_non_ui(
    kernel: Any,
    control: asyncio.Queue[Any],
    ui: asyncio.Queue[Any],
) -> None:
    kernel.handle_message.side_effect = [RuntimeError("boom"), None]
    control.put_nowait(_execute("first"))
    control.put_nowait(_execute("second"))
    control.put_nowait(StopKernelCommand())

    await listen_messages(kernel, control, ui, asyncio_queue_reader)

    # Second dispatch proves the loop survived the first raise.
    assert kernel.handle_message.await_count == 2


async def test_listen_messages_swallows_handle_message_exception_ui_branch(
    kernel: Any,
    control: asyncio.Queue[Any],
    ui: asyncio.Queue[Any],
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


async def test_listen_messages_exits_when_reader_raises(
    kernel: Any,
    control: asyncio.Queue[Any],
    ui: asyncio.Queue[Any],
) -> None:
    async def failing_reader(_queue: Any) -> Any:
        raise OSError("queue closed")

    await listen_messages(kernel, control, ui, failing_reader)

    kernel.handle_message.assert_not_called()


async def test_listen_messages_merges_ui_updates(
    kernel: Any,
    control: asyncio.Queue[Any],
    ui: asyncio.Queue[Any],
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
    dispatched = kernel.handle_message.await_args.args[0]
    assert isinstance(dispatched, UpdateUIElementCommand)
    assert dispatched.values == [2]
