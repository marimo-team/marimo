# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from marimo._runtime.commands import ModelCommand, ModelUpdateMessage
from marimo._runtime.kernel_request_handlers import KernelRequestHandlers
from marimo._types.ids import WidgetModelId

if TYPE_CHECKING:
    from tests.conftest import MockedKernel


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
