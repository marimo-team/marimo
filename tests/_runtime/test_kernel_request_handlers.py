# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._runtime.commands import (
    ExecuteCellCommand,
    ExecuteCellsCommand,
    ExecuteScratchpadCommand,
    HTTPRequest,
    ModelCommand,
    ModelUpdateMessage,
    UpdateQueryParamsCommand,
)
from marimo._runtime.kernel_request_handlers import KernelRequestHandlers
from marimo._types.ids import WidgetModelId
from tests._messaging.mocks import MockStream

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


async def test_nested_commands_complete_the_run_once(
    mocked_kernel: MockedKernel,
) -> None:
    await KernelRequestHandlers(mocked_kernel.k)._handle_execute_scratchpad(
        ExecuteScratchpadCommand(
            run_id="outer",
            notebook_cells=(),
            code=(
                "import marimo._code_mode as cm\n"
                "from marimo._runtime.commands import ExecuteCellsCommand\n"
                "await cm.get_context().execute_command(ExecuteCellsCommand("
                "cell_ids=['child'], codes=['x = 42']))"
            ),
        )
    )
    messages = MockStream(mocked_kernel.stream).operations
    assert [m["run_id"] for m in messages if m["op"] == "completed-run"] == [
        "outer"
    ]
    assert {m["run_id"] for m in messages if m["op"] == "cell-op"} == {"outer"}
    assert messages[-1]["op"] == "completed-run"


async def test_update_query_params_delegates_and_completes_the_run(
    mocked_kernel: MockedKernel,
) -> None:
    command = UpdateQueryParamsCommand(query_params={"tab": "b"})
    with patch.object(
        mocked_kernel.k, "update_query_params", new=AsyncMock()
    ) as mock_update:
        await KernelRequestHandlers(
            mocked_kernel.k
        )._handle_update_query_params(command)
    mock_update.assert_awaited_once_with(command)
    messages = MockStream(mocked_kernel.stream).operations
    assert [m["op"] for m in messages] == ["completed-run"]


async def test_update_query_params_exposes_the_http_request_to_cells(
    mocked_kernel: MockedKernel,
) -> None:
    k = mocked_kernel.k
    await k.run(
        [
            ExecuteCellCommand(cell_id="0", code="import marimo as mo"),
            ExecuteCellCommand(cell_id="1", code="params = mo.query_params()"),
            ExecuteCellCommand(
                cell_id="2",
                code=(
                    "tab = params.get('tab')\n"
                    "request = mo.app_meta().request\n"
                    "user = request.user['username'] if request else None"
                ),
            ),
        ]
    )
    assert k.globals["user"] is None

    http_request = HTTPRequest(
        url={},
        base_url={},
        headers={},
        query_params={},
        path_params={},
        cookies={},
        meta={},
        user={"username": "ada"},
    )
    await KernelRequestHandlers(k)._handle_update_query_params(
        UpdateQueryParamsCommand(
            query_params={"tab": "b"}, request=http_request
        )
    )

    # Same as a UI element update: cells re-run by this command see the
    # request that triggered it (auth-gated apps read request.user).
    assert k.globals["tab"] == "b"
    assert k.globals["user"] == "ada"


async def test_a_failed_command_flushes_before_completing(
    mocked_kernel: MockedKernel,
) -> None:
    stream = MockStream(mocked_kernel.stream)
    flushed = []

    def flush() -> None:
        flushed.append(list(stream.operations))

    with (
        patch.object(
            mocked_kernel.k, "run", side_effect=RuntimeError("failed")
        ),
        patch.object(mocked_kernel.stream, "flush_console", side_effect=flush),
        pytest.raises(RuntimeError, match="failed"),
    ):
        await KernelRequestHandlers(mocked_kernel.k)._handle_execute_multiple(
            ExecuteCellsCommand(cell_ids=[], codes=[])
        )
    assert flushed == [[]]
    assert [
        (m["op"], m["outcome"], m["error"]) for m in stream.operations
    ] == [("completed-run", "failed", "failed")]


async def test_independent_task_does_not_own_the_enclosing_cycle(
    mocked_kernel: MockedKernel,
) -> None:
    handlers = KernelRequestHandlers(mocked_kernel.k)
    await handlers._handle_execute_scratchpad(
        ExecuteScratchpadCommand(
            run_id="outer",
            notebook_cells=(),
            code=(
                "import asyncio\n"
                "import marimo._code_mode as cm\n"
                "from marimo._runtime.commands import ExecuteScratchpadCommand\n"
                "await asyncio.gather(cm.get_context().execute_command(\n"
                "    ExecuteScratchpadCommand(code='3 * 3', request=None)))\n"
                "42"
            ),
        )
    )
    messages = MockStream(mocked_kernel.stream).operations
    completed = [m for m in messages if m["op"] == "completed-run"]
    assert len(completed) == 2
    assert completed[0]["run_id"] != "outer"
    assert completed[1]["run_id"] == "outer"
    running = [
        m["run_id"]
        for m in messages
        if m["op"] == "cell-op" and m["status"] == "running"
    ]
    assert running == ["outer", completed[0]["run_id"]]


class TestReceiveModelMessage:
    @pytest.fixture
    def model_command(self) -> ModelCommand:
        return ModelCommand(
            model_id=WidgetModelId("comm-id"),
            message=ModelUpdateMessage(state={}, buffer_paths=[]),
            buffers=[],
        )

    async def test_empty_state_skips_ui_dispatch(
        self,
        mocked_kernel: MockedKernel,
        model_command: ModelCommand,
    ) -> None:
        kernel = mocked_kernel.k
        handlers = KernelRequestHandlers(kernel)

        with (
            patch(
                "marimo._runtime.kernel_request_handlers.WIDGET_COMM_MANAGER"
            ) as mock_comm_manager,
            patch.object(
                kernel,
                "set_ui_element_value",
                new=AsyncMock(),
            ) as mock_set_ui,
        ):
            mock_comm_manager.receive_comm_message.return_value = (
                "ui-element-id",
                {},
            )
            kernel.state_updates = MagicMock()
            kernel.state_updates.__bool__ = MagicMock(return_value=False)

            await handlers._handle_receive_model_message(model_command)

            mock_set_ui.assert_not_called()

    async def test_non_empty_state_dispatches(
        self,
        mocked_kernel: MockedKernel,
        model_command: ModelCommand,
    ) -> None:
        kernel = mocked_kernel.k
        handlers = KernelRequestHandlers(kernel)

        with (
            patch(
                "marimo._runtime.kernel_request_handlers.WIDGET_COMM_MANAGER"
            ) as mock_comm_manager,
            patch.object(
                kernel,
                "set_ui_element_value",
                new=AsyncMock(return_value=True),
            ) as mock_set_ui,
        ):
            mock_comm_manager.receive_comm_message.return_value = (
                "ui-element-id",
                {"value": 1},
            )

            await handlers._handle_receive_model_message(model_command)

            mock_set_ui.assert_awaited_once()


@pytest.mark.parametrize(
    "read",
    [
        "input('prompt')",
        "__import__('builtins').input()",
        "__import__('getpass').getpass()",
    ],
)
async def test_noninteractive_scratch_input_is_scoped_to_the_command(
    mocked_kernel: MockedKernel, read: str
) -> None:
    kernel = mocked_kernel.k
    handlers = KernelRequestHandlers(kernel)
    kernel.globals["observed"] = []
    await handlers._handle_execute_scratchpad(
        ExecuteScratchpadCommand(
            code=f"try:\n    {read}\nexcept EOFError:\n    observed.append('EOF')",
            allow_stdin=False,
        )
    )
    await handlers._handle_execute_scratchpad(
        ExecuteScratchpadCommand(code="observed.append(input('interactive'))")
    )
    assert kernel.globals["observed"] == ["EOF", "interactive"]
