# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock

from marimo._ai._tools.types import CodeExecutionResult
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import CellNotification
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.scratchpad import extract_result


def _make_session(
    notification: CellNotification | None = None,
) -> MagicMock:
    session = MagicMock()
    session.session_view.cell_notifications = {}
    if notification is not None:
        session.session_view.cell_notifications[SCRATCH_CELL_ID] = notification
    return session


class TestExtractResult:
    def test_no_notification(self) -> None:
        result = extract_result(_make_session())
        assert result == CodeExecutionResult(success=True)

    def test_string_output(self) -> None:
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="hello",
            ),
            console=None,
            status="idle",
        )
        result = extract_result(_make_session(notif))
        assert result.success is True
        assert result.output == "hello"

    def test_dict_output_text_plain(self) -> None:
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data={"text/plain": "value", "text/html": "<b>value</b>"},
            ),
            console=None,
            status="idle",
        )
        result = extract_result(_make_session(notif))
        assert result.output == "value"

    def test_dict_output_html_fallback(self) -> None:
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/html",
                data={"text/html": "<b>hi</b>"},
            ),
            console=None,
            status="idle",
        )
        result = extract_result(_make_session(notif))
        assert result.output == "<b>hi</b>"

    def test_stdout_stderr(self) -> None:
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=None,
            console=[
                CellOutput(
                    channel=CellChannel.STDOUT,
                    mimetype="text/plain",
                    data="out1",
                ),
                CellOutput(
                    channel=CellChannel.STDERR,
                    mimetype="text/plain",
                    data="err1",
                ),
                CellOutput(
                    channel=CellChannel.STDOUT,
                    mimetype="text/plain",
                    data="out2",
                ),
            ],
            status="idle",
        )
        result = extract_result(_make_session(notif))
        assert result.stdout == ["out1", "out2"]
        assert result.stderr == ["err1"]

    def test_errors(self) -> None:
        err_obj = MagicMock()
        err_obj.msg = "NameError: x is not defined"
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.MARIMO_ERROR,
                mimetype="application/vnd.marimo+error",
                data=[err_obj],
            ),
            console=None,
            status="idle",
        )
        result = extract_result(_make_session(notif))
        assert result.success is False
        assert len(result.errors) == 1
        assert "NameError" in result.errors[0]

    def test_none_console_entries_skipped(self) -> None:
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=None,
            console=[
                None,
                CellOutput(  # type: ignore[list-item]
                    channel=CellChannel.STDOUT,
                    mimetype="text/plain",
                    data="ok",
                ),
            ],
            status="idle",
        )
        result = extract_result(_make_session(notif))
        assert result.stdout == ["ok"]
