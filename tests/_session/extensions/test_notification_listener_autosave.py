# Copyright 2026 Marimo. All rights reserved.
"""Tests for code_mode auto-save in NotificationListenerExtension."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    DocumentChange,
    MoveCell,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
    TransactionSource,
)
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._messaging.notification import (
    AlertNotification,
    NotebookDocumentTransactionNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._messaging.types import KernelMessage
from marimo._server.models.models import SaveNotebookRequest
from marimo._session.extensions.extensions import (
    NotificationListenerExtension,
)
from marimo._session.model import SessionMode
from marimo._session.notebook import AppFileManager
from marimo._types.ids import CellId_t

INITIAL_NOTEBOOK = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def _():
    x = 1
    return (x,)

if __name__ == "__main__":
    app.run()
"""


def _make_extension(
    *, mode: SessionMode = SessionMode.EDIT
) -> NotificationListenerExtension:
    kernel_manager = Mock()
    kernel_manager.mode = mode
    queue_manager = Mock()
    queue_manager.stream_queue = None
    return NotificationListenerExtension(kernel_manager, queue_manager)


def _document_from(app_file_manager: AppFileManager) -> NotebookDocument:
    return NotebookDocument(
        [
            NotebookCell(
                id=d.cell_id, code=d.code, name=d.name, config=d.config
            )
            for d in app_file_manager.app.cell_manager.cell_data()
        ]
    )


def _serialize_tx(
    *changes: DocumentChange, source: TransactionSource = "code-mode"
) -> KernelMessage:
    return serialize_kernel_message(
        NotebookDocumentTransactionNotification(
            transaction=Transaction(changes=changes, source=source)
        )
    )


@pytest.fixture
def app_file_manager(tmp_path: Path) -> AppFileManager:
    temp_file = tmp_path / "test_autosave.py"
    temp_file.write_text(INITIAL_NOTEBOOK)
    return AppFileManager(filename=str(temp_file))


@pytest.fixture
def notebook_path(app_file_manager: AppFileManager) -> Path:
    assert app_file_manager.path is not None
    return Path(app_file_manager.path)


@pytest.fixture
def existing_cell_id(app_file_manager: AppFileManager) -> CellId_t:
    return next(iter(app_file_manager.app.cell_manager.cell_ids()))


@pytest.fixture
def session(app_file_manager: AppFileManager) -> Mock:
    s = Mock()
    s.app_file_manager = app_file_manager
    s.document = _document_from(app_file_manager)
    s.notify = Mock()
    return s


@pytest.fixture
def ext() -> NotificationListenerExtension:
    return _make_extension()


class TestKernelSourcedAutoSave:
    """Kernel-sourced transactions should persist to disk in edit mode."""

    def test_create_cell_writes_to_disk(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        notebook_path: Path,
    ) -> None:
        ext._on_kernel_message(
            session,
            _serialize_tx(
                CreateCell(
                    cell_id=CellId_t("new-cell-1"),
                    code="y = 2",
                    name="",
                    config=CellConfig(),
                )
            ),
        )
        contents = notebook_path.read_text()
        assert "y = 2" in contents
        assert "x = 1" in contents

    def test_set_code_writes_to_disk(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
        notebook_path: Path,
    ) -> None:
        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 42")),
        )
        contents = notebook_path.read_text()
        assert "x = 42" in contents
        assert "x = 1\n" not in contents

    def test_set_name_writes_to_disk(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
        notebook_path: Path,
    ) -> None:
        ext._on_kernel_message(
            session,
            _serialize_tx(SetName(cell_id=existing_cell_id, name="my_cell")),
        )
        assert "def my_cell" in notebook_path.read_text()

    def test_set_config_writes_to_disk(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
        notebook_path: Path,
    ) -> None:
        ext._on_kernel_message(
            session,
            _serialize_tx(
                SetConfig(
                    cell_id=existing_cell_id,
                    column=None,
                    disabled=False,
                    hide_code=True,
                )
            ),
        )
        contents = notebook_path.read_text()
        assert "hide_code=True" in contents or "hide_code: true" in contents

    def test_delete_cell_writes_to_disk(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
        notebook_path: Path,
    ) -> None:
        # Add a second cell first so delete doesn't leave us empty
        ext._on_kernel_message(
            session,
            _serialize_tx(
                CreateCell(
                    cell_id=CellId_t("tmp-keep"),
                    code="keeper = 99",
                    name="",
                    config=CellConfig(),
                )
            ),
        )
        ext._on_kernel_message(
            session, _serialize_tx(DeleteCell(cell_id=existing_cell_id))
        )
        contents = notebook_path.read_text()
        assert "keeper = 99" in contents
        assert "x = 1" not in contents

    def test_move_cell_writes_to_disk(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
        notebook_path: Path,
    ) -> None:
        second_id = CellId_t("second")
        ext._on_kernel_message(
            session,
            _serialize_tx(
                CreateCell(
                    cell_id=second_id,
                    code="y = 2",
                    name="",
                    config=CellConfig(),
                )
            ),
        )
        ext._on_kernel_message(
            session,
            _serialize_tx(MoveCell(cell_id=existing_cell_id, after=second_id)),
        )
        contents = notebook_path.read_text()
        assert contents.index("y = 2") < contents.index("x = 1")

    def test_notify_still_called_on_kernel_transaction(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
    ) -> None:
        """Auto-save must not suppress the frontend broadcast."""
        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 99")),
        )
        assert session.notify.called
        notif = session.notify.call_args_list[0].args[0]
        assert isinstance(notif, NotebookDocumentTransactionNotification)


class TestAutoSaveSkipped:
    """Scenarios where auto-save must be a no-op."""

    def test_client_sourced_transaction_does_not_rewrite(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
        notebook_path: Path,
    ) -> None:
        before_mtime = notebook_path.stat().st_mtime
        ext._on_kernel_message(
            session,
            _serialize_tx(
                SetCode(cell_id=existing_cell_id, code="x = 77"),
                source="frontend",
            ),
        )
        assert session.notify.called
        assert notebook_path.stat().st_mtime == before_mtime
        assert "x = 77" not in notebook_path.read_text()

    def test_run_mode_skips_autosave(
        self,
        session: Mock,
        existing_cell_id: CellId_t,
        notebook_path: Path,
    ) -> None:
        run_ext = _make_extension(mode=SessionMode.RUN)
        before_mtime = notebook_path.stat().st_mtime
        run_ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 999")),
        )
        assert notebook_path.stat().st_mtime == before_mtime


class TestUnnamedNotebook:
    """Auto-save is a silent no-op for unnamed notebooks."""

    @pytest.fixture
    def unnamed_session(self) -> tuple[Mock, CellId_t]:
        mgr = AppFileManager(filename=None)
        seed_id = next(iter(mgr.app.cell_manager.cell_ids()))
        s = Mock()
        s.app_file_manager = mgr
        s.document = _document_from(mgr)
        s.notify = Mock()
        return s, seed_id

    def test_skips_without_raising(
        self,
        ext: NotificationListenerExtension,
        unnamed_session: tuple[Mock, CellId_t],
    ) -> None:
        sess, seed_id = unnamed_session
        ext._on_kernel_message(
            sess, _serialize_tx(SetCode(cell_id=seed_id, code="x = 2"))
        )
        assert sess.notify.called

    def test_debug_log_flag_flips(
        self,
        ext: NotificationListenerExtension,
        unnamed_session: tuple[Mock, CellId_t],
    ) -> None:
        sess, seed_id = unnamed_session
        ext._on_kernel_message(
            sess, _serialize_tx(SetCode(cell_id=seed_id, code="x = 2"))
        )
        ext._on_kernel_message(
            sess, _serialize_tx(SetCode(cell_id=seed_id, code="x = 3"))
        )
        assert ext._unnamed_autosave_logged is True


def _get_alerts(session: Mock) -> list[AlertNotification]:
    """Extract every ``AlertNotification`` the interceptor broadcast."""
    return [
        call.args[0]
        for call in session.notify.call_args_list
        if isinstance(call.args[0], AlertNotification)
    ]


def _get_tx_broadcasts(
    session: Mock,
) -> list[NotebookDocumentTransactionNotification]:
    return [
        call.args[0]
        for call in session.notify.call_args_list
        if isinstance(call.args[0], NotebookDocumentTransactionNotification)
    ]


def _install_failing_write(
    app_file_manager: AppFileManager, message: str = "disk full"
) -> None:
    def _fail(*_args: object, **_kwargs: object) -> None:
        raise OSError(message)

    app_file_manager.storage.write = _fail  # type: ignore[method-assign]


class TestFailureSurfaces:
    """Write failures should surface as an AlertNotification toast."""

    @pytest.fixture
    def failing_storage(self, app_file_manager: AppFileManager) -> None:
        _install_failing_write(app_file_manager)

    @pytest.mark.usefixtures("failing_storage")
    def test_write_failure_broadcasts_alert(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
    ) -> None:
        # Must not raise out of the interceptor
        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 2")),
        )

        alerts = _get_alerts(session)
        assert len(alerts) == 1
        assert alerts[0].variant == "danger"
        assert alerts[0].title == "Auto-save failed"

    @pytest.mark.usefixtures("failing_storage")
    def test_transaction_still_broadcast_when_save_fails(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
    ) -> None:
        """Even on save failure, the frontend must see the transaction so
        its local state stays in sync with the kernel graph."""
        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 2")),
        )
        assert len(_get_tx_broadcasts(session)) == 1

    def test_alert_description_is_html_escaped(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        app_file_manager: AppFileManager,
        existing_cell_id: CellId_t,
    ) -> None:
        """User-controllable path + OS error strings must be HTML-escaped
        before landing in AlertNotification.description, which the frontend
        renders via renderHTML (sanitized today, but defense in depth)."""
        _install_failing_write(
            app_file_manager, message="<script>alert(1)</script>"
        )
        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 2")),
        )

        alerts = _get_alerts(session)
        assert len(alerts) == 1
        desc = alerts[0].description
        assert "<script>" not in desc
        assert "&lt;script&gt;" in desc


class TestCellSnapshotIsolation:
    """``_maybe_autosave`` must deep-copy cells before scheduling the
    save. ``NotebookCell`` and ``CellConfig`` are mutable and owned by
    the document, so a shallow ``list(...)`` would let the event-loop
    thread mutate fields under the worker thread's feet — a torn
    snapshot / data race."""

    def test_autosave_passes_deep_copied_cells_to_save(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
    ) -> None:
        received: list[list[NotebookCell]] = []
        real_save = session.app_file_manager.save_from_cells

        def _capture(cells: list[NotebookCell], **kwargs: object) -> str:
            received.append(list(cells))
            return real_save(cells, **kwargs)

        session.app_file_manager.save_from_cells = _capture  # type: ignore[method-assign]

        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 2")),
        )

        assert len(received) == 1
        snapshot = received[0]
        live_cells = session.document.cells
        assert len(snapshot) == len(live_cells)
        for snap_cell, live_cell in zip(snapshot, live_cells, strict=True):
            # Distinct cell objects…
            assert snap_cell is not live_cell
            # …and distinct config objects. If the config were shared,
            # a ``SetConfig`` on the loop thread would race an in-flight
            # save on the worker thread.
            assert snap_cell.config is not live_cell.config
            # Values still match at snapshot time.
            assert snap_cell.id == live_cell.id
            assert snap_cell.code == live_cell.code
            assert snap_cell.name == live_cell.name

    def test_post_submit_document_mutation_does_not_leak_into_snapshot(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        existing_cell_id: CellId_t,
    ) -> None:
        """Regression: if the shallow-copy bug returned, clobbering
        ``cell.code`` / ``cell.config`` on the document after submit
        would also clobber the snapshot the worker thread is about to
        read."""
        received: list[list[NotebookCell]] = []
        real_save = session.app_file_manager.save_from_cells

        def _capture(cells: list[NotebookCell], **kwargs: object) -> str:
            received.append(list(cells))
            return real_save(cells, **kwargs)

        session.app_file_manager.save_from_cells = _capture  # type: ignore[method-assign]

        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 2")),
        )

        for cell in session.document.cells:
            cell.code = "CLOBBERED"
            cell.name = "CLOBBERED_NAME"
            cell.config.hide_code = True

        assert len(received) == 1
        snapshot = received[0]
        assert all(c.code != "CLOBBERED" for c in snapshot)
        assert all(c.name != "CLOBBERED_NAME" for c in snapshot)
        assert all(c.config.hide_code is False for c in snapshot)


class TestLayoutPreservation:
    """Auto-save must not wipe an existing layout_file setting."""

    def test_layout_file_survives_autosave(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        app_file_manager: AppFileManager,
        existing_cell_id: CellId_t,
    ) -> None:
        app_file_manager.app.update_config(
            {"layout_file": "layouts/with_layout.grid.json"}
        )
        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="x = 2")),
        )
        assert (
            app_file_manager.app.config.layout_file
            == "layouts/with_layout.grid.json"
        )


class TestAutosaveOrdering:
    """Queued autosaves must not clobber newer foreground save state."""

    def test_stale_autosave_does_not_clobber_newer_rename_and_save(
        self,
        ext: NotificationListenerExtension,
        session: Mock,
        app_file_manager: AppFileManager,
        existing_cell_id: CellId_t,
        notebook_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        queued_work: list[tuple[object, object | None]] = []

        def _capture_submit(
            work: object, *, on_error: object | None = None
        ) -> None:
            queued_work.append((work, on_error))

        monkeypatch.setattr(ext._autosave_runner, "submit", _capture_submit)

        ext._on_kernel_message(
            session,
            _serialize_tx(SetCode(cell_id=existing_cell_id, code="old = 1")),
        )
        assert len(queued_work) == 1

        renamed_path = notebook_path.with_name("renamed_after_autosave.py")
        app_file_manager.rename(str(renamed_path))
        app_file_manager.save(
            SaveNotebookRequest(
                cell_ids=[existing_cell_id],
                filename=str(renamed_path),
                codes=["new = 2"],
                names=[""],
                configs=[CellConfig()],
            )
        )

        work, _on_error = queued_work.pop()
        assert callable(work)
        work()

        contents = renamed_path.read_text()
        assert "new = 2" in contents
        assert "old = 1" not in contents
