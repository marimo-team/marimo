# Copyright 2026 Marimo. All rights reserved.
"""Tests for file_change_handler module."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from marimo._ast.cell import CellConfig
from marimo._config.manager import get_default_config_manager
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
)
from marimo._messaging.notebook.document import NotebookCell, NotebookDocument
from marimo._messaging.notification import (
    NotebookDocumentTransactionNotification,
    ReloadNotification,
)
from marimo._runtime.commands import SyncGraphCommand
from marimo._server.models.models import SaveNotebookRequest
from marimo._session.file_change_handler import (
    EditModeReloadStrategy,
    FileChangeCoordinator,
    RunModeReloadStrategy,
    _build_reload_transaction,
)
from marimo._session.notebook import AppFileManager
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from pathlib import Path

SINGLE_CELL_NOTEBOOK = dedent(
    """\
    import marimo
    app = marimo.App()

    @app.cell
    def cell1():
        x = 1
        return x
    """
)


def _make_app(tmp_path: Path, content: str) -> AppFileManager:
    test_file = tmp_path / "test.py"
    test_file.write_text(content)
    return AppFileManager(filename=str(test_file))


def _document_from(app_file_manager: AppFileManager) -> NotebookDocument:
    cm = app_file_manager.app.cell_manager
    return NotebookDocument(
        [
            NotebookCell(
                id=cd.cell_id,
                code=cd.code,
                name=cd.name,
                config=cd.config,
            )
            for cd in cm.cell_data()
        ]
    )


def _get_transaction(mock_session: MagicMock) -> Transaction:
    calls = [
        call
        for call in mock_session.notify.call_args_list
        if isinstance(call[0][0], NotebookDocumentTransactionNotification)
    ]
    assert len(calls) == 1
    return calls[0][0][0].transaction


def _changes_of_type(tx: Transaction, cls: type) -> list:
    return [c for c in tx.changes if isinstance(c, cls)]


def _get_sync_command(mock_session: MagicMock) -> SyncGraphCommand:
    assert mock_session.put_control_request.call_count == 1
    cmd = mock_session.put_control_request.call_args[0][0]
    assert isinstance(cmd, SyncGraphCommand)
    return cmd


def _run_reload(
    tmp_path: Path,
    mock_session: MagicMock,
    config_manager,
    content: str = SINGLE_CELL_NOTEBOOK,
    document: NotebookDocument | None = None,
) -> tuple[AppFileManager, list[CellId_t]]:
    """Wire up a mock session and run EditModeReloadStrategy.handle_reload.

    Returns (app_file_manager, cell_ids) for further assertions.
    """
    afm = _make_app(tmp_path, content)
    mock_session.app_file_manager = afm
    prev_document = document if document is not None else NotebookDocument()
    mock_session.document = prev_document
    strategy = EditModeReloadStrategy(config_manager)
    cell_ids = list(afm.app.cell_manager.cell_ids())
    transaction = _build_reload_transaction(
        prev_document, afm.app.cell_manager
    )
    strategy.handle_reload(
        mock_session,
        transaction=transaction,
        changed_cell_ids=set(cell_ids),
    )
    return afm, cell_ids


DEFAULT_CELL_ID = CellId_t("cell1")


def _make_document_with_extra_cell(
    cell_ids: list[CellId_t],
    deleted_id: CellId_t = DEFAULT_CELL_ID,
) -> NotebookDocument:
    """Build a document containing cell_ids[0] plus an extra cell to be deleted."""
    return NotebookDocument(
        [
            NotebookCell(
                id=cell_ids[0],
                code="x = 1",
                name="cell1",
                config=CellConfig(),
            ),
            NotebookCell(
                id=deleted_id,
                code="y = 2",
                name="cell2",
                config=CellConfig(),
            ),
        ]
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.notify = MagicMock()
    session.put_control_request = MagicMock()
    return session


@pytest.fixture
def config_manager_lazy():
    return get_default_config_manager(current_path=None).with_overrides(
        {"runtime": {"watcher_on_save": "lazy"}}
    )


@pytest.fixture
def config_manager_autorun():
    return get_default_config_manager(current_path=None).with_overrides(
        {"runtime": {"watcher_on_save": "autorun"}}
    )


# ---------------------------------------------------------------------------
# EditModeReloadStrategy — lazy vs autorun
# ---------------------------------------------------------------------------


def test_edit_mode_reload_strategy_lazy(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    _run_reload(tmp_path, mock_session, config_manager_lazy)

    tx = _get_transaction(mock_session)
    assert len(_changes_of_type(tx, CreateCell)) == 1
    assert len(_changes_of_type(tx, ReorderCells)) == 1
    mock_session.put_control_request.assert_not_called()


def test_edit_mode_reload_strategy_autorun(
    tmp_path: Path, mock_session: MagicMock, config_manager_autorun
) -> None:
    _, cell_ids = _run_reload(tmp_path, mock_session, config_manager_autorun)

    tx = _get_transaction(mock_session)
    assert len(_changes_of_type(tx, CreateCell)) == 1

    sync_cmd = _get_sync_command(mock_session)
    assert len(sync_cmd.run_ids) == len(cell_ids)


def test_edit_mode_reload_no_deletions_lazy_no_control_request(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    afm = _make_app(tmp_path, SINGLE_CELL_NOTEBOOK)
    _run_reload(
        tmp_path,
        mock_session,
        config_manager_lazy,
        document=_document_from(afm),
    )
    mock_session.put_control_request.assert_not_called()


# ---------------------------------------------------------------------------
# EditModeReloadStrategy — deleted cells
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["lazy", "autorun"])
def test_edit_mode_reload_with_deleted_cells(
    tmp_path: Path,
    mock_session: MagicMock,
    config_manager_lazy,
    config_manager_autorun,
    mode: str,
) -> None:
    config = config_manager_lazy if mode == "lazy" else config_manager_autorun
    deleted_id = CellId_t("cell2")

    afm = _make_app(tmp_path, SINGLE_CELL_NOTEBOOK)
    mock_session.app_file_manager = afm
    cell_ids = list(afm.app.cell_manager.cell_ids())
    prev_document = _make_document_with_extra_cell(cell_ids, deleted_id)
    mock_session.document = prev_document

    strategy = EditModeReloadStrategy(config)
    transaction = _build_reload_transaction(
        prev_document, afm.app.cell_manager
    )
    strategy.handle_reload(
        mock_session,
        transaction=transaction,
        changed_cell_ids=set(cell_ids) | {deleted_id},
    )

    # Transaction should include a DeleteCell
    tx = _get_transaction(mock_session)
    deletes = _changes_of_type(tx, DeleteCell)
    assert len(deletes) == 1
    assert deletes[0].cell_id == deleted_id

    # Both modes must sync deletions to the kernel
    sync_cmd = _get_sync_command(mock_session)
    assert sync_cmd.delete_ids == [deleted_id]

    if mode == "lazy":
        assert sync_cmd.run_ids == []
    else:
        assert set(sync_cmd.run_ids) == set(cell_ids)


# ---------------------------------------------------------------------------
# EditModeReloadStrategy — transaction change types
# ---------------------------------------------------------------------------


def test_edit_mode_reload_sends_config_changes(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    content = dedent(
        """\
        import marimo
        app = marimo.App()

        @app.cell(hide_code=True)
        def my_named_cell():
            x = 1
            return x
        """
    )
    afm = _make_app(tmp_path, content)
    cell_ids = list(afm.app.cell_manager.cell_ids())
    _run_reload(
        tmp_path,
        mock_session,
        config_manager_lazy,
        content=content,
        document=NotebookDocument(
            [
                NotebookCell(
                    id=cell_ids[0],
                    code="x = 1",
                    name="my_named_cell",
                    config=CellConfig(hide_code=False),
                ),
            ]
        ),
    )

    config_changes = _changes_of_type(
        _get_transaction(mock_session), SetConfig
    )
    assert len(config_changes) == 1
    assert config_changes[0].hide_code is True


def test_edit_mode_reload_sends_name_changes(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    content = dedent(
        """\
        import marimo
        app = marimo.App()

        @app.cell
        def new_name():
            x = 1
            return x
        """
    )
    afm = _make_app(tmp_path, content)
    cell_ids = list(afm.app.cell_manager.cell_ids())
    _run_reload(
        tmp_path,
        mock_session,
        config_manager_lazy,
        content=content,
        document=NotebookDocument(
            [
                NotebookCell(
                    id=cell_ids[0],
                    code="x = 1",
                    name="old_name",
                    config=CellConfig(),
                ),
            ]
        ),
    )

    name_changes = _changes_of_type(_get_transaction(mock_session), SetName)
    assert len(name_changes) == 1
    assert name_changes[0].name == "new_name"


def test_edit_mode_reload_sends_code_changes(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    content = dedent(
        """\
        import marimo
        app = marimo.App()

        @app.cell
        def cell1():
            x = 2
            return x
        """
    )
    afm = _make_app(tmp_path, content)
    cell_ids = list(afm.app.cell_manager.cell_ids())
    _run_reload(
        tmp_path,
        mock_session,
        config_manager_lazy,
        content=content,
        document=NotebookDocument(
            [
                NotebookCell(
                    id=cell_ids[0],
                    code="x = 1",
                    name="cell1",
                    config=CellConfig(),
                ),
            ]
        ),
    )

    code_changes = _changes_of_type(_get_transaction(mock_session), SetCode)
    assert len(code_changes) == 1
    assert "x = 2" in code_changes[0].code


def test_edit_mode_reload_multiple_cells_mixed_configs(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    content = dedent(
        """\
        import marimo
        app = marimo.App()

        @app.cell(hide_code=True)
        def setup():
            import pandas as pd
            return (pd,)

        @app.cell(disabled=True)
        def disabled_cell():
            x = 1
            return x

        @app.cell
        def _():
            y = 2
            return y
        """
    )
    _run_reload(tmp_path, mock_session, config_manager_lazy, content=content)

    tx = _get_transaction(mock_session)
    creates = _changes_of_type(tx, CreateCell)
    assert len(creates) == 3
    assert len(_changes_of_type(tx, ReorderCells)) == 1

    by_name = {c.name: c for c in creates}
    assert by_name["setup"].config.hide_code is True
    assert by_name["disabled_cell"].config.disabled is True
    assert by_name["_"].config.hide_code is False
    assert by_name["_"].config.disabled is False


# ---------------------------------------------------------------------------
# AppFileManager.reload() — change detection
# ---------------------------------------------------------------------------


def _assert_reload_detects_change(
    tmp_path: Path,
    initial: str,
    modified: str,
    expected_count: int = 1,
) -> AppFileManager:
    """Write initial content, overwrite with modified, reload, and assert."""
    test_file = tmp_path / "test.py"
    test_file.write_text(initial)
    afm = AppFileManager(filename=str(test_file))
    test_file.write_text(modified)
    changed = afm.reload()
    assert len(changed) == expected_count
    return afm


_BASE_CELL = dedent(
    """\
    import marimo
    app = marimo.App()

    @app.cell
    def my_cell():
        x = 1
        return x
    """
)


def test_reload_detects_config_only_changes(tmp_path: Path) -> None:
    modified = _BASE_CELL.replace("@app.cell", "@app.cell(hide_code=True)")
    afm = _assert_reload_detects_change(tmp_path, _BASE_CELL, modified)
    assert next(iter(afm.app.cell_manager.configs())).hide_code is True


def test_reload_detects_disabled_config_change(tmp_path: Path) -> None:
    modified = _BASE_CELL.replace("@app.cell", "@app.cell(disabled=True)")
    afm = _assert_reload_detects_change(tmp_path, _BASE_CELL, modified)
    assert next(iter(afm.app.cell_manager.configs())).disabled is True


def test_reload_detects_name_only_changes(tmp_path: Path) -> None:
    initial = _BASE_CELL.replace("my_cell", "old_name")
    modified = _BASE_CELL.replace("my_cell", "new_name")
    afm = _assert_reload_detects_change(tmp_path, initial, modified)
    assert next(iter(afm.app.cell_manager.names())) == "new_name"


def test_reload_no_changes_returns_empty(tmp_path: Path) -> None:
    test_file = tmp_path / "test.py"
    test_file.write_text(SINGLE_CELL_NOTEBOOK)
    afm = AppFileManager(filename=str(test_file))
    assert len(afm.reload()) == 0


def test_reload_detects_only_changed_cell_in_multi_cell(
    tmp_path: Path,
) -> None:
    initial = dedent(
        """\
        import marimo
        app = marimo.App()

        @app.cell
        def cell_a():
            x = 1
            return x

        @app.cell
        def cell_b():
            y = 2
            return y
        """
    )
    modified = initial.replace(
        "@app.cell\ndef cell_b", "@app.cell(hide_code=True)\ndef cell_b"
    )
    afm = _assert_reload_detects_change(tmp_path, initial, modified)

    names = list(afm.app.cell_manager.names())
    configs = list(afm.app.cell_manager.configs())
    cell_ids = list(afm.app.cell_manager.cell_ids())

    assert names == ["cell_a", "cell_b"]
    assert configs[0].hide_code is False
    assert configs[1].hide_code is True
    assert afm.reload() == set()  # no further changes
    # The earlier reload should have flagged cell_b's ID
    # (already asserted by _assert_reload_detects_change returning 1)


# ---------------------------------------------------------------------------
# RunModeReloadStrategy
# ---------------------------------------------------------------------------


def test_run_mode_reload_strategy(mock_session: MagicMock) -> None:
    RunModeReloadStrategy().handle_reload(
        mock_session,
        transaction=Transaction(changes=(), source="file-watch"),
        changed_cell_ids={CellId_t("cell1")},
    )
    mock_session.notify.assert_called_once()
    assert isinstance(mock_session.notify.call_args[0][0], ReloadNotification)


# ---------------------------------------------------------------------------
# FileChangeCoordinator
# ---------------------------------------------------------------------------


async def test_file_change_coordinator_handles_change(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    test_file = tmp_path / "test.py"
    test_file.write_text(SINGLE_CELL_NOTEBOOK)
    mock_session.app_file_manager = AppFileManager(filename=str(test_file))

    strategy = MagicMock()
    coordinator = FileChangeCoordinator(strategy)

    test_file.write_text(
        SINGLE_CELL_NOTEBOOK.replace("x = 1", "x = 2  # Changed")
    )
    result = await coordinator.handle_change(test_file, mock_session)

    assert result.handled
    assert result.error is None
    strategy.handle_reload.assert_called_once()


async def test_file_change_coordinator_skips_own_writes(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    content_with_main = dedent(
        """\
        import marimo
        app = marimo.App()

        @app.cell
        def cell1():
            x = 1
            return x

        if __name__ == "__main__":
            app.run()
        """
    )
    temp_file = tmp_path / "test_own_writes.py"
    temp_file.write_text(content_with_main)

    afm = AppFileManager(filename=str(temp_file))
    mock_session.app_file_manager = afm

    cell_ids = list(afm.app.cell_manager.cell_ids())
    codes = list(afm.app.cell_manager.codes())
    afm.save(
        SaveNotebookRequest(
            cell_ids=cell_ids,
            filename=str(temp_file),
            codes=codes,
            names=["cell1"],
            configs=[CellConfig()],
            persist=True,
        )
    )

    strategy = MagicMock()
    coordinator = FileChangeCoordinator(strategy)

    # Content matches last save — should skip
    result = await coordinator.handle_change(temp_file, mock_session)
    assert not result.handled
    strategy.handle_reload.assert_not_called()

    # External edit — should reload
    temp_file.write_text(
        content_with_main.replace("x = 1", "x = 2  # Changed by editor")
    )
    result = await coordinator.handle_change(temp_file, mock_session)
    assert result.handled
    strategy.handle_reload.assert_called_once()


async def test_file_change_coordinator_handles_syntax_errors(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    """Test file change coordinator handles syntax errors gracefully."""
    content = dedent(
        """\
        import marimo
        app = marimo.App()

        @app.cell
        def cell1():
            x = 1
            return x
        """
    )
    test_file = tmp_path / "test.py"
    test_file.write_text(content)

    app_file_manager = AppFileManager(filename=str(test_file))
    mock_session.app_file_manager = app_file_manager

    strategy = MagicMock()
    coordinator = FileChangeCoordinator(strategy)

    # Write invalid syntax
    test_file.write_text(
        dedent(
            """\
            import marimo
            app = marimo.App()

            @app.cell
            def cell1():
                x = 1
                # Invalid syntax below
                def broken(
            """
        )
    )

    result = await coordinator.handle_change(test_file, session=mock_session)

    # Should handle using best-effort scanner fallback (never re-raises syntax errors)
    assert result.handled
    assert result.error is None


async def test_file_change_coordinator_path_mismatch(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    test_file = tmp_path / "test.py"
    test_file.write_text(SINGLE_CELL_NOTEBOOK)
    other_file = tmp_path / "other.py"
    other_file.write_text(SINGLE_CELL_NOTEBOOK)

    mock_session.app_file_manager = AppFileManager(filename=str(test_file))

    strategy = MagicMock()
    coordinator = FileChangeCoordinator(strategy)

    result = await coordinator.handle_change(other_file, session=mock_session)

    assert not result.handled
    assert "mismatch" in result.error.lower()


async def test_file_change_coordinator_config_only_change(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    test_file = tmp_path / "test.py"
    test_file.write_text(SINGLE_CELL_NOTEBOOK)
    mock_session.app_file_manager = AppFileManager(filename=str(test_file))

    strategy = MagicMock()
    coordinator = FileChangeCoordinator(strategy)

    test_file.write_text(
        SINGLE_CELL_NOTEBOOK.replace("@app.cell", "@app.cell(hide_code=True)")
    )
    result = await coordinator.handle_change(test_file, mock_session)

    assert result.handled
    assert result.error is None
    assert len(result.changed_cell_ids) == 1
    strategy.handle_reload.assert_called_once()
