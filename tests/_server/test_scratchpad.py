# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock

import pytest
from inline_snapshot import snapshot

from marimo._ai._tools.types import CodeExecutionResult
from marimo._code_mode.screenshot_meta import (
    SCREENSHOT_AUTH_TOKEN_KEY,
    SCREENSHOT_SERVER_URL_KEY,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import MarimoExceptionRaisedError
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
    NotificationMessage,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._runtime.commands import (
    CommandMessage,
    ExecuteScratchpadCommand,
    HTTPRequest,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.models.models import InstantiateNotebookRequest
from marimo._server.scratchpad import (
    ScratchCellListener,
    _format_console,
    _format_sse,
    build_done_event,
    extract_result,
    run_scratchpad_code,
    snapshot_for_scratchpad,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.types import Scope

    from marimo._session.session import Session

_TEST_RUN_ID = "test-run-id"


def _completed_run(run_id: str = _TEST_RUN_ID) -> CompletedRunNotification:
    return CompletedRunNotification(run_id=run_id)


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


class TestSnapshotForScratchpad:
    """Snapshot helper shared by `/api/execute` and MCP `execute_code`."""

    def test_packages_document_and_outputs(self) -> None:
        from marimo._ast.cell import CellConfig
        from marimo._messaging.notebook.document import (
            NotebookCell as DocCell,
        )
        from marimo._types.ids import CellId_t

        cell = DocCell(
            id=CellId_t("a"),
            code="print('hi'); x = 1",
            name="",
            config=CellConfig(),
        )
        output = CellOutput(
            channel=CellChannel.OUTPUT, mimetype="text/plain", data="1"
        )
        console = [CellOutput.stdout("hi\n")]

        session = MagicMock()
        session.document.cells = (cell,)
        session.document.cell_ids = (cell.id,)
        session.session_view.get_cell_outputs.return_value = {cell.id: output}
        session.session_view.get_cell_console_outputs.return_value = {
            cell.id: console
        }

        notebook_cells, cell_outputs = snapshot_for_scratchpad(session)
        assert notebook_cells == (cell,)
        assert cell_outputs.output == snapshot({"a": output})
        assert cell_outputs.console_outputs == snapshot({"a": console})


def _build_request(
    *,
    scheme: str = "http",
    host: str = "localhost",
    port: int = 1234,
):
    """Build a real Starlette Request so ``HTTPRequest.from_request``
    can read it without an exhaustive MagicMock setup."""
    from starlette.requests import Request

    scope: Scope = {
        "type": "http",
        "method": "POST",
        "scheme": scheme,
        "server": (host, port),
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"host", f"{host}:{port}".encode())],
    }
    return Request(scope)


class _FakeSession:
    """Minimal duck-typed Session for ``run_scratchpad_code`` tests.

    Behaves like a real Session in the ways the runner cares about:

    * ``scoped`` registers a listener for the duration of the context.
    * ``put_control_request`` routes a ``CompletedRunNotification`` to
      the active listener so ``listener.wait()`` returns naturally —
      no need to monkey-patch listener internals.

    Set ``auto_complete=False`` to drive the timeout path (the listener
    will never see a completion event).
    """

    document: SimpleNamespace
    session_view: SimpleNamespace
    scratchpad_lock: asyncio.Lock
    control_requests: list[CommandMessage]
    instantiate_calls: list[
        tuple[InstantiateNotebookRequest, HTTPRequest | None]
    ]
    interrupt_count: int
    _auto_complete: bool
    _active_listener: ScratchCellListener | None
    _pre_complete_notifs: list[NotificationMessage]

    def __init__(self, *, auto_complete: bool = True) -> None:
        self.document = SimpleNamespace(cells=())
        self.session_view = SimpleNamespace(cell_notifications={})
        self.scratchpad_lock = asyncio.Lock()
        self.control_requests = []
        self.instantiate_calls = []
        self.interrupt_count = 0
        self._auto_complete = auto_complete
        self._active_listener = None
        self._pre_complete_notifs = []

    def as_session(self) -> Session:
        """Type-only cast to ``Session`` for the runner's signature."""
        return cast("Session", cast(object, self))

    def emit(self, notification: NotificationMessage) -> None:
        """Schedule a notification to be delivered to the active
        listener just before the auto-generated completion event."""
        self._pre_complete_notifs.append(notification)

    @contextmanager
    def scoped(
        self, listener: ScratchCellListener
    ) -> Iterator[ScratchCellListener]:
        self._active_listener = listener
        try:
            yield listener
        finally:
            self._active_listener = None

    def instantiate(
        self,
        request: InstantiateNotebookRequest,
        *,
        http_request: HTTPRequest | None,
    ) -> None:
        self.instantiate_calls.append((request, http_request))

    def put_control_request(
        self,
        req: CommandMessage,
        from_consumer_id: object = None,
    ) -> None:
        del from_consumer_id
        self.control_requests.append(req)
        if not (
            self._auto_complete
            and isinstance(req, ExecuteScratchpadCommand)
            and self._active_listener is not None
        ):
            return
        session = self.as_session()
        for notif in self._pre_complete_notifs:
            self._active_listener.on_notification_sent(
                session, serialize_kernel_message(notif)
            )
        self._active_listener.on_notification_sent(
            session,
            serialize_kernel_message(
                CompletedRunNotification(run_id=req.run_id)
            ),
        )

    def try_interrupt(self) -> None:
        self.interrupt_count += 1


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

    def test_child_cell_errors_included(self) -> None:
        """extract_result reports failure when listener saw child errors."""
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="summary",
            ),
            console=None,
            status="idle",
        )
        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
        listener.child_error_summaries.append(
            "cell 'abc12345' raised ZeroDivisionError"
        )
        result = extract_result(_make_session(notif), listener)
        assert result.success is False
        assert result.errors == ["cell 'abc12345' raised ZeroDivisionError"]

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
    # ``done`` shape is uniform ``{success, output}``. Failures always
    # carry an empty output — the actual error detail was streamed via
    # preceding ``stderr`` events.
    _EMPTY = {"mimetype": "text/plain", "data": ""}

    def test_no_notification(self) -> None:
        event, data = _parse_sse(build_done_event(_make_session()))
        assert event == "done"
        assert data == snapshot({"success": True, "output": self._EMPTY})

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
        assert data == snapshot(
            {
                "success": True,
                "output": {"mimetype": "text/plain", "data": "42"},
            }
        )

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
        assert data == snapshot(
            {
                "success": True,
                "output": {"mimetype": "text/plain", "data": "value"},
            }
        )

    def test_scratch_cell_error(self) -> None:
        """Scratch cell's own MARIMO_ERROR marks the done event as failed;
        the traceback itself is in preceding stderr events, not here."""
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
        assert data == snapshot({"success": False, "output": self._EMPTY})

    def test_child_cell_error_reports_failure(self) -> None:
        """done event reports failure when listener saw child errors."""
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="summary",
            ),
            status="idle",
        )
        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
        listener.child_error_summaries.append(
            "cell 'abc12345' raised ZeroDivisionError"
        )
        _, data = _parse_sse(build_done_event(_make_session(notif), listener))
        assert data == snapshot({"success": False, "output": self._EMPTY})

    def test_no_child_errors_still_succeeds(self) -> None:
        """done event succeeds when listener has no child errors."""
        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
        notif = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="42",
            ),
            status="idle",
        )
        _, data = _parse_sse(build_done_event(_make_session(notif), listener))
        assert data == snapshot(
            {
                "success": True,
                "output": {"mimetype": "text/plain", "data": "42"},
            }
        )


class TestScratchCellListener:
    @pytest.mark.asyncio
    async def test_stream_basic(self) -> None:
        from marimo._messaging.serde import serialize_kernel_message

        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
        event_bus = MagicMock()
        session = MagicMock()
        listener.on_attach(session, event_bus)

        running = CellNotification(cell_id=SCRATCH_CELL_ID, status="running")
        console = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=CellOutput.stdout("hello\n"),
        )
        idle = CellNotification(cell_id=SCRATCH_CELL_ID, status="idle")

        for notif in [running, console, idle, _completed_run()]:
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

    @pytest.mark.asyncio
    async def test_ignores_unrelated_completed_run(self) -> None:
        """CompletedRun with a different run_id must NOT fire the sentinel."""
        import asyncio

        from marimo._messaging.serde import serialize_kernel_message

        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
        event_bus = MagicMock()
        session = MagicMock()
        listener.on_attach(session, event_bus)

        # A CompletedRun from an unrelated command (e.g. session.instantiate)
        listener.on_notification_sent(
            session, serialize_kernel_message(_completed_run("other-run-id"))
        )

        # Consumer should still be blocked — no sentinel fired.
        got_event = asyncio.Event()

        async def consume() -> None:
            async for _ in listener.stream():
                got_event.set()

        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(got_event.wait(), timeout=0.1)
            raise AssertionError("listener exited on wrong run_id")
        except asyncio.TimeoutError:
            pass
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    @pytest.mark.asyncio
    async def test_ignores_other_cell_status(self) -> None:
        """Status-only notifications from non-scratch cells are ignored."""
        from marimo._messaging.serde import serialize_kernel_message

        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
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
    async def test_captures_other_cell_console(self) -> None:
        """Console output from non-scratch cells is captured."""
        from marimo._messaging.serde import serialize_kernel_message

        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
        event_bus = MagicMock()
        session = MagicMock()
        listener.on_attach(session, event_bus)

        other_console = CellNotification(
            cell_id="other_cell_id",
            console=CellOutput.stderr("error trace\n"),
        )
        listener.on_notification_sent(
            session, serialize_kernel_message(other_console)
        )
        assert not listener._queue.empty()

        listener.on_notification_sent(
            session, serialize_kernel_message(_completed_run())
        )

        events: list[str] = []
        async for event in listener.stream():
            events.append(event)

        assert len(events) == 1
        name, payload = _parse_sse(events[0])
        assert name == "stderr"
        assert payload["data"] == "error trace\n"

    @pytest.mark.asyncio
    async def test_stream_cancelled_on_disconnect(self) -> None:
        """stream() can be cancelled externally (simulating client disconnect)."""
        import asyncio

        from marimo._messaging.serde import serialize_kernel_message

        listener = ScratchCellListener(run_id=_TEST_RUN_ID)
        event_bus = MagicMock()
        session = MagicMock()
        listener.on_attach(session, event_bus)

        # Send one stdout event but no sentinel — stream would block forever
        console = CellNotification(
            cell_id=SCRATCH_CELL_ID,
            console=CellOutput.stdout("partial\n"),
        )
        listener.on_notification_sent(
            session, serialize_kernel_message(console)
        )

        events: list[str] = []
        got_first_event = asyncio.Event()

        async def consume() -> None:
            async for event in listener.stream():
                events.append(event)
                got_first_event.set()

        task = asyncio.create_task(consume())
        await got_first_event.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Got the partial event before cancellation
        assert len(events) == 1
        name, payload = _parse_sse(events[0])
        assert name == "stdout"
        assert payload["data"] == "partial\n"


class TestRunScratchpadCode:
    """Regression guards for ``run_scratchpad_code`` — the runner that
    backs the AI ``execute_code`` tool."""

    @staticmethod
    def _execute_command(session: _FakeSession) -> ExecuteScratchpadCommand:
        cmds = [
            c
            for c in session.control_requests
            if isinstance(c, ExecuteScratchpadCommand)
        ]
        assert len(cmds) == 1, (
            f"expected one ExecuteScratchpadCommand, got {session.control_requests!r}"
        )
        return cmds[0]

    @pytest.mark.asyncio
    async def test_stamps_screenshot_meta_and_run_id_on_command(
        self,
    ) -> None:
        """Regression guard: ``run_id`` and screenshot meta must reach
        the ``ExecuteScratchpadCommand`` unchanged. Without ``run_id``,
        ``ScratchCellListener`` filters out the completion event and
        every code-mode tool call hangs ~30s before timing out."""
        session = _FakeSession()

        result = await run_scratchpad_code(
            session.as_session(),
            _build_request(),
            code="x = 1",
            server_url="http://localhost:1234",
            auth_token="fake-token",
        )

        assert result.success is True
        cmd = self._execute_command(session)
        assert cmd.run_id is not None
        assert cmd.request is not None
        assert cmd.request.meta[SCREENSHOT_SERVER_URL_KEY] == (
            "http://localhost:1234"
        )
        assert cmd.request.meta[SCREENSHOT_AUTH_TOKEN_KEY] == "fake-token"

    @pytest.mark.asyncio
    async def test_instantiates_session_without_auto_run(self) -> None:
        """The runner must seed the dependency graph before executing
        (so ``_code_mode.run_cell`` can resolve cell IDs) but it must
        NOT auto-run the notebook's cells."""
        session = _FakeSession()

        await run_scratchpad_code(
            session.as_session(),
            _build_request(),
            code="x = 1",
            server_url="u",
            auth_token="t",
        )

        assert len(session.instantiate_calls) == 1
        instantiate_req, _ = session.instantiate_calls[0]
        assert instantiate_req.auto_run is False

    @pytest.mark.asyncio
    async def test_holds_scratchpad_lock_while_putting_execute_command(
        self,
    ) -> None:
        """``scratchpad_lock`` must be held while putting the execute
        command so two concurrent code-mode calls can't interleave."""
        session = _FakeSession()
        lock_held: list[bool] = []
        original_put = session.put_control_request

        def spy(req: CommandMessage, from_consumer_id: object = None) -> None:
            if isinstance(req, ExecuteScratchpadCommand):
                lock_held.append(session.scratchpad_lock.locked())
            original_put(req, from_consumer_id)

        session.put_control_request = spy  # type: ignore[method-assign]

        await run_scratchpad_code(
            session.as_session(),
            _build_request(),
            code="x = 1",
            server_url="u",
            auth_token="t",
        )

        assert lock_held == [True]

    @pytest.mark.asyncio
    async def test_timeout_interrupts_kernel_and_surfaces_in_errors(
        self,
    ) -> None:
        """On timeout the kernel is still running the (likely hung)
        scratchpad code; ``run_scratchpad_code`` must interrupt it so the
        next code-mode call doesn't block on ``scratchpad_lock`` — and
        the timeout must be reported in ``errors`` (plural), matching
        the success path's shape."""
        session = _FakeSession(auto_complete=False)

        result = await run_scratchpad_code(
            session.as_session(),
            _build_request(),
            code="while True: pass",
            server_url="u",
            auth_token="t",
            timeout=0.05,
        )

        assert result == snapshot(
            CodeExecutionResult(
                success=False,
                errors=["Execution timed out after 0.05s"],
            )
        )
        assert session.interrupt_count == 1

    @pytest.mark.asyncio
    async def test_timeout_interrupt_happens_while_holding_lock(
        self,
    ) -> None:
        """Regression guard: ``try_interrupt()`` must run BEFORE releasing
        ``scratchpad_lock``. Otherwise a concurrent code-mode call could
        acquire the lock and start running between timeout detection and
        the interrupt — and get its brand-new execution killed by us."""
        session = _FakeSession(auto_complete=False)
        lock_held_during_interrupt: list[bool] = []
        original_interrupt = session.try_interrupt

        def spy() -> None:
            lock_held_during_interrupt.append(session.scratchpad_lock.locked())
            original_interrupt()

        session.try_interrupt = spy  # type: ignore[method-assign]

        await run_scratchpad_code(
            session.as_session(),
            _build_request(),
            code="while True: pass",
            server_url="u",
            auth_token="t",
            timeout=0.05,
        )

        assert lock_held_during_interrupt == [True]

    @pytest.mark.asyncio
    async def test_child_cell_errors_flow_into_result_errors(self) -> None:
        """End-to-end: child-cell errors captured by the listener during
        execution must surface in ``result.errors`` — otherwise the AI
        never learns its ``run_cell`` calls failed. This pins down the
        ``extract_result(session, listener)`` plumbing as well; dropping
        the ``listener`` arg silently loses every child-cell error."""
        from marimo._types.ids import CellId_t

        session = _FakeSession()
        # Real scratch cell runs emit an idle notification even when
        # their own output is empty; without one, extract_result
        # short-circuits before consulting the listener.
        session.session_view.cell_notifications[SCRATCH_CELL_ID] = (
            CellNotification(
                cell_id=SCRATCH_CELL_ID,
                output=CellOutput(
                    channel=CellChannel.OUTPUT,
                    mimetype="text/plain",
                    data="",
                ),
                console=None,
                status="idle",
            )
        )
        session.emit(
            CellNotification(
                cell_id=CellId_t("child-cell"),
                output=CellOutput.errors(
                    [
                        MarimoExceptionRaisedError(
                            msg="division by zero",
                            exception_type="ZeroDivisionError",
                            raising_cell=None,
                        )
                    ]
                ),
                console=None,
                status="idle",
            )
        )

        result = await run_scratchpad_code(
            session.as_session(),
            _build_request(),
            code="run_cell('child-cell')",
            server_url="u",
            auth_token="t",
        )

        assert result.success is False
        assert result.errors == ["cell 'child-cell' raised ZeroDivisionError"]
