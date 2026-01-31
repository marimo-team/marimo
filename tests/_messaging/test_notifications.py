# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._ast.toplevel import HINT_UNPARSABLE, TopLevelStatus
from marimo._messaging.notification import (
    CellNotification,
    InstallingPackageAlertNotification,
    ListPackagesResultNotification,
    PackagesDependencyTreeResultNotification,
    StartupLogsNotification,
    UIElementMessageNotification,
)
from marimo._messaging.notification_utils import (
    CellNotificationUtils,
    broadcast_notification,
)
from marimo._messaging.variables import create_variable_value
from marimo._output.hypertext import Html
from marimo._plugins.ui._impl.input import slider
from marimo._runtime.packages.utils import PackageDescription
from marimo._types.ids import CellId_t
from marimo._utils.parse_dataclass import parse_raw
from marimo._utils.uv_tree import DependencyTreeNode
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


def test_installing_package_alert_basic() -> None:
    """Test basic InstallingPackageAlert without streaming logs."""
    alert = InstallingPackageAlertNotification(
        packages={"numpy": "queued", "pandas": "installing"}
    )
    assert alert.name == "installing-package-alert"
    assert alert.packages == {"numpy": "queued", "pandas": "installing"}
    assert alert.logs is None
    assert alert.log_status is None


def test_installing_package_alert_with_logs() -> None:
    """Test InstallingPackageAlert with streaming logs."""
    packages = {"numpy": "installing"}
    logs = {"numpy": "Installing numpy...\n"}

    alert = InstallingPackageAlertNotification(
        packages=packages, logs=logs, log_status="start"
    )

    assert alert.name == "installing-package-alert"
    assert alert.packages == packages
    assert alert.logs == logs
    assert alert.log_status == "start"


def test_send_ui_element_message_broadcast() -> None:
    """Test SendUIElementMessage broadcasting and serialization."""
    stream = MockStream()

    msg = UIElementMessageNotification(
        ui_element="test_element",
        model_id=None,
        message={"action": "update", "value": 42},
        buffers=[b"buffer1", b"buffer2"],
    )

    broadcast_notification(msg, stream)

    assert len(stream.messages) == 1

    assert stream.operations[0] == {
        "op": "send-ui-element-message",
        "ui_element": "test_element",
        "model_id": None,
        "message": {"action": "update", "value": 42},
        "buffers": [
            "YnVmZmVyMQ==",
            "YnVmZmVyMg==",
        ],
    }

    assert stream.parsed_operations[0] == msg


def test_list_packages_result_notification() -> None:
    """Test ListPackagesResultNotification creation and serialization."""
    stream = MockStream()

    packages = [
        PackageDescription(name="numpy", version="1.24.0"),
        PackageDescription(name="pandas", version="2.0.0"),
    ]
    msg = ListPackagesResultNotification(
        request_id="test-request-id",
        packages=packages,
    )

    assert msg.name == "list-packages-result"
    assert msg.request_id == "test-request-id"
    assert len(msg.packages) == 2
    assert msg.packages[0].name == "numpy"

    broadcast_notification(msg, stream)

    assert len(stream.messages) == 1
    assert stream.operations[0]["op"] == "list-packages-result"
    assert stream.operations[0]["request_id"] == "test-request-id"
    assert len(stream.operations[0]["packages"]) == 2


def test_packages_dependency_tree_result_notification() -> None:
    """Test PackagesDependencyTreeResultNotification creation and serialization."""
    stream = MockStream()

    tree = DependencyTreeNode(
        name="marimo",
        version="0.10.0",
        tags=[],
        dependencies=[
            DependencyTreeNode(
                name="starlette",
                version="0.37.0",
                tags=[],
                dependencies=[],
            )
        ],
    )
    msg = PackagesDependencyTreeResultNotification(
        request_id="test-request-id",
        tree=tree,
    )

    assert msg.name == "packages-dependency-tree-result"
    assert msg.request_id == "test-request-id"
    assert msg.tree is not None
    assert msg.tree.name == "marimo"
    assert len(msg.tree.dependencies) == 1

    broadcast_notification(msg, stream)

    assert len(stream.messages) == 1
    assert stream.operations[0]["op"] == "packages-dependency-tree-result"
    assert stream.operations[0]["request_id"] == "test-request-id"
    assert stream.operations[0]["tree"]["name"] == "marimo"


def test_packages_dependency_tree_result_notification_none_tree() -> None:
    """Test PackagesDependencyTreeResultNotification with None tree."""
    stream = MockStream()

    msg = PackagesDependencyTreeResultNotification(
        request_id="test-request-id",
        tree=None,
    )

    assert msg.tree is None

    broadcast_notification(msg, stream)

    assert len(stream.messages) == 1
    assert stream.operations[0]["op"] == "packages-dependency-tree-result"
    assert stream.operations[0]["tree"] is None
