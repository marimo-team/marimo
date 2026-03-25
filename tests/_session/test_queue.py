# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import Mock

from marimo._runtime.commands import (
    CodeCompletionCommand,
    ModelCommand,
    ModelUpdateMessage,
    StopKernelCommand,
    UpdateUIElementCommand,
)
from marimo._session.queue import route_control_request


class TestRouteControlRequest:
    def _make_queues(self) -> tuple[Mock, Mock, Mock]:
        return Mock(), Mock(), Mock()

    def test_completion_goes_to_completion_queue_only(self) -> None:
        control, completion, ui_element = self._make_queues()
        cmd = CodeCompletionCommand(id="r1", document="x.", cell_id="c1")

        route_control_request(cmd, control, completion, ui_element)

        completion.put.assert_called_once_with(cmd)
        control.put.assert_not_called()
        ui_element.put.assert_not_called()

    def test_ui_element_goes_to_both_queues(self) -> None:
        control, completion, ui_element = self._make_queues()
        cmd = UpdateUIElementCommand(object_ids=["ui1"], values=[42])

        route_control_request(cmd, control, completion, ui_element)

        control.put.assert_called_once_with(cmd)
        ui_element.put.assert_called_once_with(cmd)
        completion.put.assert_not_called()

    def test_model_command_goes_to_both_queues(self) -> None:
        control, completion, ui_element = self._make_queues()
        cmd = ModelCommand(
            model_id="m1",
            message=ModelUpdateMessage(state={}, buffer_paths=[]),
            buffers=[],
        )

        route_control_request(cmd, control, completion, ui_element)

        control.put.assert_called_once_with(cmd)
        ui_element.put.assert_called_once_with(cmd)
        completion.put.assert_not_called()

    def test_regular_command_goes_to_control_queue_only(self) -> None:
        control, completion, ui_element = self._make_queues()
        cmd = StopKernelCommand()

        route_control_request(cmd, control, completion, ui_element)

        control.put.assert_called_once_with(cmd)
        completion.put.assert_not_called()
        ui_element.put.assert_not_called()
