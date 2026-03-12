# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from marimo._ai._tools.types import CodeExecutionResult
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    MarimoExceptionRaisedError,
    MarimoSyntaxError,
)
from marimo._messaging.notification import CellNotification
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.scratchpad import (
    StreamingScratchCellListener,
    _format_console,
    _format_sse,
    build_done_event,
    build_timeout_event,
    extract_result,
)


def _make_session(
    notification: CellNotification | None = None,
) -> MagicMock:
    session = MagicMock()
    session.session_view.cell_notifications = {}
    if notification is not None:
        session.session_view.cell_notifications[SCRATCH_CELL_ID] = notification
    return session


def _parse_sse(sse: str) -> tuple[str, dict[str, object]]:
    """Parse an SSE string into (event_name, json_data)."""
    event = ""
    data = ""
    for line in sse.strip().splitlines():
        if line.startswith("event: "):
            event = line[len("event: ") :]
        elif line.startswith("data: "):
            data = line[len("data: ") :]
    return event, json.loads(data)


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


class TestFormatSse:
    def test_json_payload(self) -> None:
        result = _format_sse("done", {"success": True})
        assert result == 'event: done\ndata: {"success": true}\n\n'

    def test_newlines_in_json_are_escaped(self) -> None:
        result = _format_sse("stdout", {"data": "line1\nline2\n"})
        # The JSON string escapes \n, so it's a single data: line
        assert result.count("\ndata: ") == 1
        event, payload = _parse_sse(result)
        assert event == "stdout"
        assert payload["data"] == "line1\nline2\n"


class TestFormatConsole:
    def test_stdout(self) -> None:
        msg = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=CellOutput.stdout("hello world\n"),
        )
        events = _format_console(msg)
        assert len(events) == 1
        event, payload = _parse_sse(events[0])
        assert event == "stdout"
        assert payload["data"] == "hello world\n"

    def test_stderr(self) -> None:
        msg = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=CellOutput.stderr("warning\n"),
        )
        events = _format_console(msg)
        assert len(events) == 1
        event, payload = _parse_sse(events[0])
        assert event == "stderr"
        assert payload["data"] == "warning\n"

    def test_list_of_outputs(self) -> None:
        msg = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=[
                CellOutput.stdout("line1\n"),
                CellOutput.stderr("err1\n"),
            ],
        )
        events = _format_console(msg)
        assert len(events) == 2
        assert _parse_sse(events[0])[0] == "stdout"
        assert _parse_sse(events[1])[0] == "stderr"

    def test_none_console(self) -> None:
        msg = CellNotification(cell_id=SCRATCH_CELL_ID)
        assert _format_console(msg) == []

    def test_none_entries_skipped(self) -> None:
        msg = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=[
                None,  # type: ignore[list-item]
                CellOutput.stdout("ok\n"),
            ],
        )
        events = _format_console(msg)
        assert len(events) == 1

    def test_multiline_data_stays_single_sse_line(self) -> None:
        msg = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=CellOutput.stdout("a\nb\nc\n"),
        )
        events = _format_console(msg)
        assert len(events) == 1
        # Should be exactly one data: line (newlines escaped in JSON)
        assert events[0].count("\ndata: ") == 1
        _, payload = _parse_sse(events[0])
        assert payload["data"] == "a\nb\nc\n"


class TestBuildDoneEvent:
    def test_no_notification(self) -> None:
        event, data = _parse_sse(build_done_event(_make_session()))
        assert event == "done"
        assert data == {"success": True}

    def test_success_with_output(self) -> None:
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="42",
            ),
            status="idle",
        )
        _, data = _parse_sse(build_done_event(_make_session(notif)))
        assert data["success"] is True
        assert data["output"]["mimetype"] == "text/plain"
        assert data["output"]["data"] == "42"

    def test_success_with_dict_output(self) -> None:
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data={"text/plain": "value", "text/html": "<b>v</b>"},
            ),
            status="idle",
        )
        _, data = _parse_sse(build_done_event(_make_session(notif)))
        assert data["success"] is True
        assert data["output"]["data"] == "value"

    def test_error_with_exception(self) -> None:
        err = MarimoExceptionRaisedError(
            msg="NameError: x is not defined",
            exception_type="NameError",
            raising_cell=None,
        )
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput.errors([err]),
            status="idle",
        )
        _, data = _parse_sse(build_done_event(_make_session(notif)))
        assert data["success"] is False
        assert data["error"]["type"] == "MarimoExceptionRaisedError"
        assert data["error"]["exception_type"] == "NameError"
        assert "NameError" in data["error"]["msg"]

    def test_error_without_exception_type(self) -> None:
        err = MarimoSyntaxError(msg="invalid syntax", lineno=1)
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput.errors([err]),
            status="idle",
        )
        _, data = _parse_sse(build_done_event(_make_session(notif)))
        assert data["success"] is False
        assert data["error"]["type"] == "MarimoSyntaxError"
        assert "exception_type" not in data["error"]

    def test_timeout(self) -> None:
        _, data = _parse_sse(build_timeout_event(30.0))
        assert data["success"] is False
        assert data["error"]["type"] == "TimeoutError"
        assert "30.0s" in data["error"]["msg"]


class TestStreamingScratchCellListener:
    @pytest.mark.asyncio
    async def test_stream_basic(self) -> None:
        from marimo._messaging.serde import serialize_kernel_message

        listener = StreamingScratchCellListener()
        event_bus = MagicMock()
        session = MagicMock()
        listener.on_attach(session, event_bus)

        running = CellNotification(cell_id=SCRATCH_CELL_ID, status="running")
        console = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=CellOutput.stdout("hello\n"),
        )
        idle = CellNotification(cell_id=SCRATCH_CELL_ID, status="idle")

        for notif in [running, console, idle]:
            listener.on_notification_sent(
                session, serialize_kernel_message(notif)
            )

        events: list[str] = []
        async for event in listener.stream():
            events.append(event)

        # running has no console → no events; console has stdout; idle has no console
        assert len(events) == 1
        name, payload = _parse_sse(events[0])
        assert name == "stdout"
        assert payload["data"] == "hello\n"
        assert not listener.timed_out

    @pytest.mark.asyncio
    async def test_ignores_other_cells(self) -> None:
        from marimo._messaging.serde import serialize_kernel_message

        listener = StreamingScratchCellListener()
        event_bus = MagicMock()
        session = MagicMock()
        listener.on_attach(session, event_bus)

        other_cell = CellNotification(
            cell_id="other_cell_id",
            status="running",  # type: ignore[arg-type]
        )
        listener.on_notification_sent(
            session, serialize_kernel_message(other_cell)
        )
        assert listener._queue.empty()

    @pytest.mark.asyncio
    async def test_stream_timeout(self) -> None:
        listener = StreamingScratchCellListener()
        event_bus = MagicMock()
        session = MagicMock()
        listener.on_attach(session, event_bus)

        events: list[str] = []
        async for event in listener.stream(timeout=0.1):
            events.append(event)

        assert events == []
        assert listener.timed_out is True
