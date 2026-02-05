# Copyright 2026 Marimo. All rights reserved.
"""File change handling for marimo notebooks.

Provides strategies for handling file changes in different session modes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol

from marimo import _loggers
from marimo._config.manager import MarimoConfigManager
from marimo._messaging.notification import (
    ReloadNotification,
    UpdateCellCodesNotification,
    UpdateCellIdsNotification,
)
from marimo._runtime.commands import DeleteCellCommand, SyncGraphCommand
from marimo._session.model import SessionMode
from marimo._types.ids import CellId_t
from marimo._utils import async_path

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._session.types import Session


@dataclass
class FileChangeResult:
    """Result of handling a file change."""

    handled: bool
    error: Optional[str] = None
    changed_cell_ids: Optional[set[CellId_t]] = None


class ReloadStrategy(Protocol):
    """Protocol for file reload strategies."""

    def handle_reload(
        self, session: Session, *, changed_cell_ids: set[CellId_t]
    ) -> None:
        """Handle reloading after file change.

        Args:
            session: The session to reload
            changed_cell_ids: Set of cell IDs that changed
        """
        ...


class EditModeReloadStrategy(ReloadStrategy):
    """Reload strategy for edit mode.

    In edit mode, we update cell IDs and codes, and optionally auto-run
    changed cells based on configuration.
    """

    def __init__(self, config_manager: MarimoConfigManager) -> None:
        self._config_manager = config_manager

    def handle_reload(
        self, session: Session, *, changed_cell_ids: set[CellId_t]
    ) -> None:
        """Handle reload in edit mode with optional auto-run."""
        # Get the latest codes and cell IDs
        codes = list(session.app_file_manager.app.cell_manager.codes())
        cell_ids = list(session.app_file_manager.app.cell_manager.cell_ids())

        LOGGER.info(
            f"File changed: {session.app_file_manager.path}. "
            f"num_cell_ids: {len(cell_ids)}, num_codes: {len(codes)}, "
            f"changed_cell_ids: {changed_cell_ids}"
        )

        # Send the updated cell IDs to the frontend
        session.notify(
            UpdateCellIdsNotification(cell_ids=cell_ids),
            from_consumer_id=None,
        )

        # Check if we should auto-run cells based on config
        watcher_on_save = self._config_manager.get_config()["runtime"][
            "watcher_on_save"
        ]
        should_autorun = watcher_on_save == "autorun"

        # Determine deleted cells
        deleted = {
            cell_id for cell_id in changed_cell_ids if cell_id not in cell_ids
        }

        # Auto-run cells if configured
        if should_autorun:
            changed_cell_ids_list = list(changed_cell_ids - deleted)
            cells = dict(zip(cell_ids, codes))

            session.put_control_request(
                SyncGraphCommand(
                    cells=cells,
                    run_ids=changed_cell_ids_list,
                    delete_ids=list(deleted),
                ),
                from_consumer_id=None,
            )
        else:
            # Just send deletes and code updates
            for to_delete in deleted:
                session.put_control_request(
                    DeleteCellCommand(cell_id=to_delete),
                    from_consumer_id=None,
                )
            if cell_ids:
                session.notify(
                    UpdateCellCodesNotification(
                        cell_ids=cell_ids,
                        codes=codes,
                        code_is_stale=True,
                    ),
                    from_consumer_id=None,
                )


class RunModeReloadStrategy:
    """Reload strategy for run mode.

    In run mode, we simply send a reload operation to the frontend.
    """

    def handle_reload(
        self, session: Session, *, changed_cell_ids: set[CellId_t]
    ) -> None:
        """Handle reload in run mode by sending Reload operation."""
        del changed_cell_ids
        session.notify(ReloadNotification(), from_consumer_id=None)


class FileChangeCoordinator:
    """Coordinates file change handling with proper locking and strategies.

    This class handles the complexities of file watching, including
    preventing duplicate reloads and delegating to mode-specific strategies.
    """

    def __init__(
        self,
        reload_strategy: ReloadStrategy,
    ) -> None:
        """Initialize the file change coordinator.

        Args:
            reload_strategy: Strategy for handling reloads
        """
        self._reload_strategy = reload_strategy
        # Track ongoing file change operations to prevent duplicates
        self._file_change_locks: dict[str, asyncio.Lock] = {}

    async def handle_change(
        self, file_path: Path, session: Session
    ) -> FileChangeResult:
        """Handle a file change for a session.

        This method reloads the notebook and sends appropriate operations
        to the frontend when a marimo file is modified.

        Args:
            file_path: The path to the file that changed
            session: The session associated with the file

        Returns:
            FileChangeResult indicating success or failure
        """
        abs_file_path = await async_path.abspath(file_path)

        # Use a lock to prevent concurrent processing of the same file
        if str(abs_file_path) not in self._file_change_locks:
            self._file_change_locks[str(abs_file_path)] = asyncio.Lock()

        async with self._file_change_locks[str(abs_file_path)]:
            return self._handle_file_change_locked(abs_file_path, session)

    def _handle_file_change_locked(
        self, file_path: str, session: Session
    ) -> FileChangeResult:
        """Handle file change with lock already acquired.

        Args:
            file_path: Absolute path to the file that changed
            session: The session associated with the file

        Returns:
            FileChangeResult indicating success or failure
        """
        LOGGER.debug(f"{file_path} was modified, handling {session}")

        # Verify the session is for this file
        if session.app_file_manager.path != file_path:
            return FileChangeResult(
                handled=False,
                error=f"Session path mismatch: {session.app_file_manager.path} != {file_path}",
            )

        # Check if the file content matches the last save
        # to avoid reloading our own writes
        if session.app_file_manager.file_content_matches_last_save():
            LOGGER.debug(
                f"File {file_path} content matches last save, skipping reload"
            )
            return FileChangeResult(handled=False)

        # Reload the file manager to get the latest code
        try:
            changed_cell_ids = session.app_file_manager.reload()
        except Exception as e:
            # If there are syntax errors, we just skip
            # and don't send the changes
            LOGGER.error(f"Error loading file: {e}")
            return FileChangeResult(handled=False, error=str(e))

        # Delegate to the reload strategy
        self._reload_strategy.handle_reload(
            session, changed_cell_ids=changed_cell_ids
        )
        return FileChangeResult(
            handled=True, changed_cell_ids=changed_cell_ids
        )


def create_reload_strategy(
    mode: SessionMode, config_manager: MarimoConfigManager
) -> ReloadStrategy:
    """Factory function to create the appropriate reload strategy.

    Args:
        mode: The session mode
        config_manager: Configuration manager

    Returns:
        The appropriate reload strategy for the mode
    """
    if mode == SessionMode.EDIT:
        return EditModeReloadStrategy(config_manager)
    else:
        return RunModeReloadStrategy()
