# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.document import NotebookCell
from marimo._messaging.notebook.outputs import CellOutputs
from marimo._runtime.commands import (
    CancelScratchpadCommand,
    CommandMessage,
    ExecuteScratchpadCommand,
    HTTPRequest,
    OutOfBandCommand,
    ScheduleScratchpadCommand,
    kebab_case,
)
from marimo._types.ids import CellId_t


def test_kebab_case() -> None:
    assert kebab_case("SomeSQLCommand") == "some-sql"
    assert kebab_case("SomeSQL") == "some-sql"
    assert kebab_case("MyNotificationCommand") == "my-notification"


def test_scheduled_scratchpad_preserves_request_and_snapshot_over_ipc() -> (
    None
):
    request = HTTPRequest(
        url={"path": "/api/kernel/execute"},
        base_url={},
        headers={},
        query_params={},
        path_params={},
        cookies={},
        meta={"screenshot_server_url": "http://localhost:2718"},
        user={},
    )
    command = ScheduleScratchpadCommand(
        execution=ExecuteScratchpadCommand(
            code="print(42)",
            request=request,
            notebook_cells=(
                NotebookCell(
                    id=CellId_t("cell"),
                    code="x = 42",
                    name="",
                    config=CellConfig(),
                ),
            ),
            cell_outputs=CellOutputs(output={}, console_outputs={}),
            run_id="scheduled",
        )
    )
    encoded = msgspec.msgpack.encode(command)
    assert msgspec.msgpack.decode(encoded, type=OutOfBandCommand) == command
    assert msgspec.msgpack.decode(encoded, type=CommandMessage) == command


def test_scratchpad_cancellation_round_trips_over_ipc() -> None:
    command = CancelScratchpadCommand(run_id="cancelled")
    encoded = msgspec.msgpack.encode(command)
    assert msgspec.msgpack.decode(encoded, type=OutOfBandCommand) == command
