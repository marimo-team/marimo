# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

import msgspec
import pytest

from marimo._ast.toplevel import HINT_UNPARSABLE, TopLevelStatus
from marimo._messaging.notification import (
    CellNotification,
    EnvironmentOperationNotification,
    EnvironmentOperationStatus,
    ModelLifecycleNotification,
    ModelOpen,
    OperationCancelled,
    OperationFailed,
    OperationRestartRequired,
    OperationRunning,
    OperationSucceeded,
    StartupLogsNotification,
    UIElementMessageNotification,
)
from marimo._messaging.notification_utils import (
    CellNotificationUtils,
    broadcast_notification,
)
from marimo._messaging.serde import (
    deserialize_kernel_message,
    serialize_kernel_message,
)
from marimo._messaging.types import KernelMessage
from marimo._messaging.variables import create_variable_value
from marimo._output.hypertext import Html
from marimo._plugins.ui._impl.input import slider
from marimo._types.ids import CellId_t
from marimo._utils.parse_dataclass import parse_raw
from tests._messaging.mocks import MockStream


def test_value_ui_element() -> None:
    variable_value = create_variable_value(
        name="s", value=slider(1, 10, value=5)
    )
    assert variable_value.datatype == "slider"
    assert variable_value.value == "5"


def test_value_html() -> None:
    h = Html("<span></span>")
    variable_value = create_variable_value(name="h", value=h)
    assert variable_value.datatype == "Html"
    assert variable_value.value == h.text


def test_variable_value_broken_str() -> None:
    class Broken:
        def __str__(self) -> str:
            raise BaseException  # noqa: TRY002

    variable_value = create_variable_value(name="o", value=Broken())
    assert variable_value.datatype == "Broken"
    assert variable_value.value is not None
    assert variable_value.value.startswith("<Broken object at")


def test_broadcast_serialization() -> None:
    cell_id = CellId_t("test_cell_id")

    stream = MockStream()
    status = MagicMock(TopLevelStatus)
    status.hint = HINT_UNPARSABLE

    CellNotificationUtils.broadcast_serialization(
        cell_id=cell_id, serialization=status, stream=stream
    )

    assert len(stream.messages) == 1
    assert stream.operations[0]["serialization"] == str(HINT_UNPARSABLE)
    cell_notification = stream.operations[0]

    assert isinstance(
        parse_raw(cell_notification, CellNotification), CellNotification
    )


def test_startup_logs_creation() -> None:
    startup_log = StartupLogsNotification(
        content="Starting up...", status="start"
    )
    assert startup_log.name == "startup-logs"
    assert startup_log.content == "Starting up..."
    assert startup_log.status == "start"


def test_startup_logs_all_statuses() -> None:
    for status in ["start", "append", "done"]:
        startup_log = StartupLogsNotification(
            content=f"Test {status}", status=status
        )
        assert startup_log.status == status
        assert startup_log.content == f"Test {status}"


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (OperationRunning(), {"kind": "running"}),
        (OperationSucceeded(), {"kind": "succeeded"}),
        (
            OperationRestartRequired(reason="Python version changed"),
            {"kind": "restart-required", "reason": "Python version changed"},
        ),
        (
            OperationFailed(error="Could not resolve dependencies"),
            {"kind": "failed", "error": "Could not resolve dependencies"},
        ),
        (OperationCancelled(), {"kind": "cancelled"}),
    ],
)
def test_environment_operation_wire_format(
    status: EnvironmentOperationStatus,
    expected: dict[str, str],
) -> None:
    notification = EnvironmentOperationNotification(
        action="install",
        source="kernel",
        logs={},
        log_mode="append",
        operation_id="install",
        status=status,
        packages={},
    )
    encoded = serialize_kernel_message(notification)
    assert msgspec.json.decode(encoded) == {
        "op": "environment-operation",
        "action": "install",
        "source": "kernel",
        "logs": {},
        "log_mode": "append",
        "operation_id": "install",
        "status": expected,
        "packages": {},
    }
    assert deserialize_kernel_message(encoded) == notification


@pytest.mark.parametrize(
    "status",
    [
        {"kind": "failed"},
        {"kind": "restart-required"},
        {"kind": "succeeded", "error": "Could not resolve dependencies"},
        "running",
    ],
)
def test_installation_status_rejects_invalid_wire_state(
    status: object,
) -> None:
    message = KernelMessage(
        msgspec.json.encode(
            {
                "op": "environment-operation",
                "operation_id": "install",
                "action": "install",
                "source": "kernel",
                "logs": {},
                "log_mode": "append",
                "packages": {},
                "status": status,
            }
        )
    )
    with pytest.raises(msgspec.ValidationError):
        deserialize_kernel_message(message)


def test_send_ui_element_message_broadcast() -> None:
    """Test SendUIElementMessage broadcasting and serialization."""
    stream = MockStream()

    msg = UIElementMessageNotification(
        ui_element="test_element",
        message={"action": "update", "value": 42},
        buffers=[b"buffer1", b"buffer2"],
    )

    broadcast_notification(msg, stream)

    assert len(stream.messages) == 1

    assert stream.operations[0] == {
        "op": "send-ui-element-message",
        "ui_element": "test_element",
        "message": {"action": "update", "value": 42},
        "buffers": [
            "YnVmZmVyMQ==",
            "YnVmZmVyMg==",
        ],
    }

    assert stream.parsed_operations[0] == msg


def test_model_lifecycle_notification_to_json_serializable() -> None:
    """to_json_serializable must not double-encode buffers (regression test)."""
    notif = ModelLifecycleNotification(
        model_id="model-1",
        message=ModelOpen(
            state={"value": 42},
            buffer_paths=[["data"]],
            buffers=[b"hello"],
        ),
    )

    result = notif.to_json_serializable()
    assert result["message"]["buffers"] == ["aGVsbG8="]
