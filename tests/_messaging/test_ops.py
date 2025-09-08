# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._ast.toplevel import HINT_UNPARSABLE, TopLevelStatus
from marimo._messaging.ops import (
    CellOp,
    InstallingPackageAlert,
    StartupLogs,
    VariableValue,
)
from marimo._output.hypertext import Html
from marimo._plugins.ui._impl.input import slider
from marimo._types.ids import CellId_t
from marimo._utils.parse_dataclass import parse_raw
from tests._messaging.mocks import MockStream


def test_value_ui_element() -> None:
    variable_value = VariableValue.create(
        name="s", value=slider(1, 10, value=5)
    )
    assert variable_value.datatype == "slider"
    assert variable_value.value == "5"


def test_value_html() -> None:
    h = Html("<span></span>")
    variable_value = VariableValue.create(name="h", value=h)
    assert variable_value.datatype == "Html"
    assert variable_value.value == h.text


def test_variable_value_broken_str() -> None:
    class Broken:
        def __str__(self) -> str:
            raise BaseException  # noqa: TRY002

    variable_value = VariableValue.create(name="o", value=Broken())
    assert variable_value.datatype == "Broken"
    assert variable_value.value is not None
    assert variable_value.value.startswith("<Broken object at")


def test_broadcast_serialization() -> None:
    cell_id = CellId_t("test_cell_id")

    stream = MockStream()
    status = MagicMock(TopLevelStatus)
    status.hint = HINT_UNPARSABLE

    CellOp.broadcast_serialization(
        cell_id=cell_id, serialization=status, stream=stream
    )

    assert len(stream.messages) == 1
    assert stream.operations[0]["serialization"] == str(HINT_UNPARSABLE)
    cell_op = stream.operations[0]

    assert isinstance(parse_raw(cell_op, CellOp), CellOp)


def test_startup_logs_creation() -> None:
    startup_log = StartupLogs(content="Starting up...", status="start")
    assert startup_log.name == "startup-logs"
    assert startup_log.content == "Starting up..."
    assert startup_log.status == "start"


def test_startup_logs_all_statuses() -> None:
    for status in ["start", "append", "done"]:
        startup_log = StartupLogs(content=f"Test {status}", status=status)
        assert startup_log.status == status
        assert startup_log.content == f"Test {status}"


def test_installing_package_alert_basic() -> None:
    """Test basic InstallingPackageAlert without streaming logs."""
    alert = InstallingPackageAlert(
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

    alert = InstallingPackageAlert(
        packages=packages, logs=logs, log_status="start"
    )

    assert alert.name == "installing-package-alert"
    assert alert.packages == packages
    assert alert.logs == logs
    assert alert.log_status == "start"
