# Copyright 2024 Marimo. All rights reserved.
"""Tests for file_change_handler module."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from marimo._ast.cell import CellConfig
from marimo._config.manager import get_default_config_manager
from marimo._messaging.notifcation import (
    Reload,
    UpdateCellCodes,
    UpdateCellIdsRequest,
)
from marimo._runtime.requests import DeleteCellRequest, SyncGraphRequest
from marimo._server.models.models import SaveNotebookRequest
from marimo._server.notebook import AppFileManager
from marimo._server.sessions.file_change_handler import (
    EditModeReloadStrategy,
    FileChangeCoordinator,
    RunModeReloadStrategy,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from pathlib import Path


def create_test_app_file_manager(
    tmp_path: Path, content: str
) -> AppFileManager:
    """Create a test app file manager with the given content."""
    test_file = tmp_path / "test.py"
    test_file.write_text(content)
    return AppFileManager(filename=str(test_file))


@pytest.fixture
def mock_session():
    """Create a mock session for testing."""
    session = MagicMock()
    session.notify = MagicMock()
    session.put_control_request = MagicMock()
    return session


@pytest.fixture
def config_manager_lazy():
    """Create a config manager with lazy watcher mode."""
    return get_default_config_manager(current_path=None).with_overrides(
        {"runtime": {"watcher_on_save": "lazy"}}
    )


@pytest.fixture
def config_manager_autorun():
    """Create a config manager with autorun watcher mode."""
    return get_default_config_manager(current_path=None).with_overrides(
        {"runtime": {"watcher_on_save": "autorun"}}
    )


def test_edit_mode_reload_strategy_lazy(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    """Test edit mode reload strategy with lazy mode."""
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
    app_file_manager = create_test_app_file_manager(tmp_path, content)
    mock_session.app_file_manager = app_file_manager

    strategy = EditModeReloadStrategy(config_manager_lazy)
    # Get actual cell IDs from the app
    cell_ids = list(app_file_manager.app.cell_manager.cell_ids())
    changed_cell_ids = set(cell_ids)

    strategy.handle_reload(mock_session, changed_cell_ids=changed_cell_ids)

    # Should send UpdateCellIdsRequest
    assert mock_session.notify.call_count >= 1
    update_ids_calls = [
        call
        for call in mock_session.notify.call_args_list
        if isinstance(call[0][0], UpdateCellIdsRequest)
    ]
    assert len(update_ids_calls) == 1

    # Should send UpdateCellCodes with code_is_stale=True
    update_codes_calls = [
        call
        for call in mock_session.notify.call_args_list
        if isinstance(call[0][0], UpdateCellCodes)
    ]
    assert len(update_codes_calls) == 1
    assert update_codes_calls[0][0][0].code_is_stale is True

    # Should not send execution requests
    mock_session.put_control_request.assert_not_called()


def test_edit_mode_reload_strategy_autorun(
    tmp_path: Path, mock_session: MagicMock, config_manager_autorun
) -> None:
    """Test edit mode reload strategy with autorun mode."""
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
    app_file_manager = create_test_app_file_manager(tmp_path, content)
    mock_session.app_file_manager = app_file_manager

    strategy = EditModeReloadStrategy(config_manager_autorun)
    changed_cell_ids = {CellId_t("cell1")}

    strategy.handle_reload(mock_session, changed_cell_ids=changed_cell_ids)

    # Should send UpdateCellIdsRequest
    assert mock_session.notify.call_count >= 1
    update_ids_calls = [
        call
        for call in mock_session.notify.call_args_list
        if isinstance(call[0][0], UpdateCellIdsRequest)
    ]
    assert len(update_ids_calls) == 1

    # Should send SyncGraphRequest for execution
    assert mock_session.put_control_request.call_count >= 1
    sync_calls = [
        call
        for call in mock_session.put_control_request.call_args_list
        if isinstance(call[0][0], SyncGraphRequest)
    ]
    assert len(sync_calls) == 1


def test_edit_mode_reload_strategy_with_deleted_cells(
    tmp_path: Path, mock_session: MagicMock, config_manager_lazy
) -> None:
    """Test edit mode reload strategy with deleted cells."""
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
    app_file_manager = create_test_app_file_manager(tmp_path, content)
    mock_session.app_file_manager = app_file_manager

    strategy = EditModeReloadStrategy(config_manager_lazy)
    # Get actual cell IDs from the app
    cell_ids = list(app_file_manager.app.cell_manager.cell_ids())
    # Indicate that cell2 was deleted (it's in changed but not in current cells)
    changed_cell_ids = set(cell_ids) | {CellId_t("cell2")}

    strategy.handle_reload(mock_session, changed_cell_ids=changed_cell_ids)

    # Should send DeleteCellRequest for cell2
    delete_calls = [
        call
        for call in mock_session.put_control_request.call_args_list
        if isinstance(call[0][0], DeleteCellRequest)
    ]
    assert len(delete_calls) == 1
    assert delete_calls[0][0][0].cell_id == CellId_t("cell2")


def test_run_mode_reload_strategy(mock_session: MagicMock) -> None:
    """Test run mode reload strategy sends Reload operation."""
    strategy = RunModeReloadStrategy()
    changed_cell_ids = {CellId_t("cell1")}

    strategy.handle_reload(mock_session, changed_cell_ids=changed_cell_ids)

    # Should send Reload operation
    mock_session.notify.assert_called_once()
    operation = mock_session.notify.call_args[0][0]
    assert isinstance(operation, Reload)


async def test_file_change_coordinator_handles_change(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    """Test file change coordinator handles file changes."""
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

    # Modify the file
    test_file.write_text(
        dedent(
            """\
            import marimo
            app = marimo.App()

            @app.cell
            def cell1():
                x = 2  # Changed
                return x
            """
        )
    )

    result = await coordinator.handle_change(test_file, mock_session)

    # Should handle the change
    assert result.handled
    assert result.error is None
    strategy.handle_reload.assert_called_once()


async def test_file_change_coordinator_skips_own_writes(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    """Test that file change coordinator skips reloading when it detects its own writes."""
    # Create a temporary file with initial content
    temp_file = tmp_path / "test_own_writes.py"
    temp_file.write_text(
        dedent(
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
    )

    # Set up app file manager
    app_file_manager = AppFileManager(filename=str(temp_file))
    mock_session.app_file_manager = app_file_manager

    # Save the file to track the last saved content
    cell_ids = list(app_file_manager.app.cell_manager.cell_ids())
    codes = list(app_file_manager.app.cell_manager.codes())
    app_file_manager.save(
        SaveNotebookRequest(
            cell_ids=cell_ids,
            filename=str(temp_file),
            codes=codes,
            names=["cell1"],
            configs=[CellConfig()],
            persist=True,
        )
    )

    # Create file change coordinator
    strategy = MagicMock()
    coordinator = FileChangeCoordinator(strategy)

    # Call handle_change - should skip reload because content matches
    result = await coordinator.handle_change(temp_file, mock_session)

    # Verify reload was NOT called (early return triggered)
    assert not result.handled
    strategy.handle_reload.assert_not_called()

    # Now externally modify the file
    temp_file.write_text(
        dedent(
            """\
            import marimo
            app = marimo.App()

            @app.cell
            def cell1():
                x = 2  # Changed by external editor
                return x

            if __name__ == "__main__":
                app.run()
            """
        )
    )

    # Call handle_change again - should now trigger reload
    result = await coordinator.handle_change(temp_file, mock_session)

    # Verify reload WAS called (content changed externally)
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

    # Should not handle due to error
    assert not result.handled
    assert result.error is not None


async def test_file_change_coordinator_path_mismatch(
    tmp_path: Path, mock_session: MagicMock
) -> None:
    """Test file change coordinator with path mismatch."""
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

    other_file = tmp_path / "other.py"
    other_file.write_text(content)

    app_file_manager = AppFileManager(filename=str(test_file))
    mock_session.app_file_manager = app_file_manager

    strategy = MagicMock()
    coordinator = FileChangeCoordinator(strategy)

    # Try to handle change for different file
    result = await coordinator.handle_change(other_file, session=mock_session)

    # Should not handle due to path mismatch
    assert not result.handled
    assert "mismatch" in result.error.lower()
