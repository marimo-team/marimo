# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._ast import load
from marimo._ast.app import App, InternalApp
from marimo._ast.app_config import overloads_from_env
from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.changes import (
    CreateCell,
    DeleteCell,
    DocumentChange,
    ReorderCells,
    SetCode,
    SetConfig,
    SetName,
    Transaction,
)
from marimo._runtime.layout.layout import (
    LayoutConfig,
    read_layout_config,
    save_layout_config,
)
from marimo._schemas.serialization import Header, NotebookSerializationV1
from marimo._server.app_defaults import AppDefaults
from marimo._session.notebook.serializer import get_notebook_serializer
from marimo._session.notebook.storage import (
    FilesystemStorage,
    StorageInterface,
)
from marimo._types.ids import CellId_t
from marimo._utils.http import HTTPException, HTTPStatus
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.scripts import with_python_version_requirement

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._ast.cell_manager import CellManager
    from marimo._messaging.notebook.document import NotebookCell
    from marimo._server.models.models import (
        CopyNotebookRequest,
        SaveNotebookRequest,
    )


def canonicalize_filename(filename: str) -> str:
    # If its not a valid Python or Markdown file, then add .py
    if not MarimoPath.is_valid_path(filename):
        filename += ".py"
    return os.path.expanduser(filename)


class AppFileManager:
    """Manages notebook file operations.

    Responsibilities:
    - App lifecycle management (loading, reloading, state tracking)
    - Coordination between storage backends and serialization
    - Configuration and layout management
    """

    def __init__(
        self,
        filename: str | Path | None,
        *,
        storage: StorageInterface | None = None,
        defaults: AppDefaults | None = None,
    ) -> None:
        self._filename = _maybe_path(filename)

        self.storage: StorageInterface = storage or FilesystemStorage()

        # Configuration defaults
        self._defaults = defaults or AppDefaults()

        # Load the app
        self.app = self._load_app(self.path)

        # Track the last saved content to avoid reloading our own writes
        self._last_saved_content: str | None = None

        # Serializes concurrent writers. Reentrant so public entry points
        # can wrap the full "mutate app + _save_file" sequence while
        # ``_save_file`` re-acquires for any direct caller.
        self._save_lock = threading.RLock()
        # Foreground writes supersede queued autosaves.
        self._autosave_generation = 0

    @property
    def filename(self) -> str | None:
        """Get the current filename as a Path object."""
        return str(self._filename) if self._filename is not None else None

    @filename.setter
    def filename(self, value: str | Path | None) -> None:
        """Set the filename, automatically converting strings to Path objects."""
        self._filename = _maybe_path(value)

    @staticmethod
    def from_app(
        app: InternalApp,
        filename: str | Path | None = None,
    ) -> AppFileManager:
        """Create AppFileManager from an existing InternalApp.

        Args:
            app: The internal app to wrap
            filename: Optional source path for the notebook. When set,
                ``AppMetadata.filename`` (and therefore ``__file__`` /
                ``mo.notebook_dir()`` inside cells) resolves to the source
                file rather than the host process's ``__main__``.

        Returns:
            AppFileManager instance
        """
        manager = AppFileManager(None)
        # Snapshot to an absolute path at assignment time so a later
        # ``chdir`` cannot change which file ``self.path`` resolves to.
        manager.filename = (
            os.path.abspath(str(filename)) if filename is not None else None
        )
        manager.app = app
        return manager

    def reload(self) -> tuple[Transaction, set[CellId_t]]:
        """Reload the app from storage.

        Splices the existing ``CellManager`` into the freshly loaded
        ``InternalApp`` so ``app.cell_manager`` and
        ``app.cell_manager.document`` identity is preserved across reload.
        The diff between old and new state is applied to the existing
        document via ``apply()``, which advances ``_version`` monotonically
        and stamps the returned transaction.

        Returns:
            ``(transaction, changed_cell_ids)``. ``transaction`` is
            stamped with the post-apply document version and is suitable
            for broadcasting to consumers. ``changed_cell_ids`` are the
            ids whose code, name, or config changed, plus all created
            and deleted ids (reorder-only is excluded).
        """
        current_cell_manager = self.app.cell_manager
        new_app = self._load_app(self.path)
        new_app.cell_manager.sort_cell_ids_by_similarity(current_cell_manager)

        transaction, changed_cell_ids = _build_transaction(
            prev=current_cell_manager, new=new_app.cell_manager
        )
        transaction = current_cell_manager.document.apply(transaction)

        # Carry over CellManager state that NotebookDocument doesn't track.
        # clear()+update() preserves dict identity, matching the invariant
        # established by CellManager._replace_state_from.
        current_cell_manager._compiled_cells.clear()
        current_cell_manager._compiled_cells.update(
            new_app.cell_manager._compiled_cells
        )
        current_cell_manager.unparsable = new_app.cell_manager.unparsable
        current_cell_manager._cell_id_generator.seen_ids |= (
            new_app.cell_manager._cell_id_generator.seen_ids
        )

        # Splice the preserved cell_manager into new_app, then swap the
        # wrapper. App-level fields (_config, _header, _filename,
        # _unparsable) come along automatically — no field enumeration.
        new_app._app._cell_manager = current_cell_manager
        self.app = new_app

        return transaction, changed_cell_ids

    def _is_same_path(self, path: Path) -> bool:
        """Check if the given path is the same as the current filename.

        Args:
            path: Path to compare

        Returns:
            True if paths refer to the same location
        """
        if self._filename is None:
            return False
        return self.storage.is_same_path(self._filename, path)

    def _assert_path_does_not_exist(self, path: Path) -> None:
        """Ensure path doesn't exist, raise HTTPException if it does.

        Args:
            path: Path to check

        Raises:
            HTTPException: If path already exists
        """
        if self.storage.exists(path):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"File {path} already exists",
            )

    def _save_file(
        self,
        path: Path,
        *,
        notebook: NotebookSerializationV1,
        persist: bool,
        previous_path: Path | None = None,
    ) -> str:
        """Save notebook to storage using appropriate format handler.

        All file writes go through this method under ``_save_lock``.

        Args:
            path: Target file path
            notebook: Notebook in IR format
            persist: Whether to actually write to storage
            previous_path: Previous file path (for format conversions)

        Returns:
            Serialized notebook contents
        """
        LOGGER.debug("Saving app to %s", path)

        with self._save_lock:
            # Get the header in case it was modified by the user (e.g. package installation)
            handler = get_notebook_serializer(path)
            header: str | None = None
            if previous_path and previous_path.exists():
                header = handler.extract_header(previous_path)
            elif path.exists():
                header = handler.extract_header(path)

            # For new .py files in sandbox mode, generate header with marimo
            if header is None and str(path).endswith(".py"):
                from marimo._config.settings import GLOBAL_SETTINGS

                if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
                    from marimo._utils.scripts import (
                        write_pyproject_to_script,
                    )

                    header = write_pyproject_to_script(
                        with_python_version_requirement(
                            {
                                "dependencies": ["marimo"],
                            }
                        )
                    )

            # Rewrap with header if relevant and set filename.
            notebook = NotebookSerializationV1(
                app=notebook.app,
                header=Header(value=header) if header else notebook.header,
                cells=notebook.cells,
                violations=notebook.violations,
                valid=notebook.valid,
                filename=str(path),
            )
            contents = handler.serialize(notebook)

            if persist:
                self.storage.write(path, contents)
                # Record the last saved content to avoid reloading our own writes
                self._last_saved_content = contents.strip()

            # If this is a new unnamed notebook, update the filename
            if self._is_unnamed():
                self._filename = path

            return contents

    def _load_app(self, path: str | None) -> InternalApp:
        """Load app from storage.

        Args:
            path: Path to load from (None for new notebooks)

        Returns:
            Loaded InternalApp instance
        """
        # Load app using existing loader
        app = load.load_app(path)
        default = overloads_from_env()

        if app is None:
            # Create new empty app with defaults
            kwargs: dict[str, Any] = default.asdict()

            # Add custom defaults if provided
            if self._defaults.width is not None:
                kwargs["width"] = self._defaults.width
            if self._defaults.auto_download is not None:
                kwargs["auto_download"] = self._defaults.auto_download
            if self._defaults.sql_output is not None:
                kwargs["sql_output"] = self._defaults.sql_output

            empty_app = InternalApp(App(**kwargs))
            empty_app.cell_manager.register_cell(
                cell_id=None,
                code="",
                config=CellConfig(),
            )
            return empty_app

        # Manually extend config defaults
        app._config.update(default.asdict_difference())

        result = InternalApp(app)
        # Ensure at least one cell
        result.cell_manager.ensure_one_cell()
        return result

    def rename(self, new_filename: str | Path) -> str:
        """Rename the notebook file.

        Args:
            new_filename: New filename (will be canonicalized)

        Returns:
            The filename of the new file.

        Raises:
            HTTPException: If rename fails or target exists
        """
        new_path = Path(canonicalize_filename(str(new_filename)))

        with self._save_lock:
            if self._is_same_path(new_path):
                return new_path.name

            self._assert_path_does_not_exist(new_path)
            self._invalidate_autosaves()

            if self._filename is not None:
                self.storage.rename(self._filename, new_path)
            else:
                # Create new file for unnamed notebooks
                self.storage.write(new_path, "")

            previous_filename = self._filename
            self._filename = new_path
            self.app._app._filename = str(new_path)

            self._save_file(
                new_path,
                notebook=self.app.to_ir(),
                persist=True,
                previous_path=previous_filename,
            )

            return new_path.name

    def read_layout_config(self) -> LayoutConfig | None:
        """Read layout configuration file.

        Returns:
            Layout configuration or None if not configured
        """
        if self.app.config.layout_file is not None and self._filename:
            app_dir = self._filename.parent
            layout = read_layout_config(app_dir, self.app.config.layout_file)
            return layout

        return None

    def read_css_file(self) -> str | None:
        """Read custom CSS file.

        Returns:
            CSS content or None if not configured
        """
        css_file = self.app.config.css_file
        if not css_file or not self._filename:
            return None
        return self.storage.read_related_file(self._filename, css_file)

    def read_html_head_file(self) -> str | None:
        """Read custom HTML head file.

        Returns:
            HTML head content or None if not configured
        """
        html_head_file = self.app.config.html_head_file
        if not html_head_file or not self._filename:
            return None
        return self.storage.read_related_file(self._filename, html_head_file)

    @property
    def path(self) -> str | None:
        """Get absolute path to notebook file as string.

        Returns:
            Absolute path as string or None if unnamed
        """
        if self._filename is None:
            return None
        return os.path.abspath(str(self._filename))

    def save_app_config(self, config: dict[str, Any]) -> str:
        """Save app configuration.

        Args:
            config: Configuration dictionary

        Returns:
            Serialized notebook content
        """
        with self._save_lock:
            self.app.update_config(config)
            if self._filename is not None:
                self._invalidate_autosaves()
                return self._save_file(
                    self._filename,
                    notebook=self.app.to_ir(),
                    persist=True,
                )
            return ""

    def save(self, request: SaveNotebookRequest) -> str:
        """Save the notebook.

        Args:
            request: Save request with cell data and options

        Returns:
            Serialized notebook content

        Raises:
            HTTPException: If save fails or tries to rename
        """
        cell_ids, codes, configs, names, filename, layout = (
            request.cell_ids,
            request.codes,
            request.configs,
            request.names,
            request.filename,
            request.layout,
        )

        filename_path = Path(canonicalize_filename(filename))

        with self._save_lock:
            # Update app with new cell data
            self.app.with_data(
                cell_ids=cell_ids,
                codes=codes,
                names=names,
                configs=configs,
            )

            if self.is_notebook_named and not self._is_same_path(
                filename_path
            ):
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    detail="Save handler cannot rename files.",
                )

            # Save layout if provided
            if layout is not None:
                app_dir = filename_path.parent
                app_name = filename_path.name
                layout_filename = save_layout_config(
                    app_dir, app_name, LayoutConfig(**layout)
                )
                self.app.update_config({"layout_file": layout_filename})
            else:
                # Remove the layout from the config
                self.app.update_config({"layout_file": None})

            if request.persist:
                self._invalidate_autosaves()
            return self._save_file(
                filename_path,
                notebook=self.app.to_ir(),
                persist=request.persist,
            )

    def capture_autosave_target(self) -> tuple[Path | None, int]:
        with self._save_lock:
            return self._filename, self._autosave_generation

    def save_from_cells(
        self,
        cells: Sequence[NotebookCell],
        *,
        expected_filename: Path | None = None,
        expected_generation: int | None = None,
    ) -> str:
        """Persist the notebook from a snapshot of document cells.

        Used by the server-side auto-save path for ``code_mode``
        mutations. Unlike ``save()``, this takes cells directly — the
        caller is responsible for snapshotting ``session.document.cells``
        on a thread where the document is quiescent.

        Raises:
            HTTPException: If the notebook is unnamed or the write fails
        """
        if self._filename is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Cannot save an unnamed notebook",
            )

        with self._save_lock:
            if expected_generation is not None:
                if expected_generation != self._autosave_generation:
                    return ""
            if expected_filename is not None:
                if self._filename is None or not self._is_same_path(
                    expected_filename
                ):
                    return ""

            self.app.with_data(
                cell_ids=[cell.id for cell in cells],
                codes=[cell.code for cell in cells],
                names=[cell.name for cell in cells],
                configs=[cell.config for cell in cells],
            )
            return self._save_file(
                self._filename,
                notebook=self.app.to_ir(),
                persist=True,
            )

    def _invalidate_autosaves(self) -> None:
        self._autosave_generation += 1

    def copy(self, request: CopyNotebookRequest) -> str:
        """Copy a notebook file.

        Args:
            request: Copy request with source and destination

        Returns:
            Basename of destination file

        Raises:
            HTTPException: If source doesn't exist, destination exists, or copy fails
        """
        source = Path(request.source)
        destination = Path(request.destination)

        # Validate source exists
        if not self.storage.exists(source):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Source file {source} does not exist",
            )

        # Check destination doesn't already exist
        self._assert_path_does_not_exist(destination)

        try:
            content = self.storage.read(source)
            self.storage.write(destination, content)
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as err:
            raise HTTPException(
                status_code=HTTPStatus.SERVER_ERROR,
                detail=f"Failed to copy from {source} to {destination}",
            ) from err

        return destination.name

    def to_code(self) -> str:
        """Convert app to Python code without saving.

        Returns:
            Python code representation of the notebook
        """
        from marimo._convert.converters import MarimoConvert

        return MarimoConvert.from_ir(self.app.to_ir()).to_py()

    def _is_unnamed(self) -> bool:
        """Check if notebook is unnamed.

        Returns:
            True if filename is None
        """
        return self._filename is None

    @property
    def is_notebook_named(self) -> bool:
        """Check if notebook has a name.

        Returns:
            True if filename is not None
        """
        return self._filename is not None

    def read_file(self) -> str:
        """Read the current file contents from storage.

        Returns:
            File contents as string

        Raises:
            HTTPException: If notebook is unnamed or read fails
        """
        if self._filename is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail="Cannot read code from an unnamed notebook",
            )
        return self.storage.read(self._filename)

    def file_content_matches_last_save(self) -> bool:
        """Check if current file content matches the last save.

        Used to avoid reloading the file when we detect our own writes.

        Returns:
            True if content matches last save, False otherwise
        """
        if self._filename is None or self._last_saved_content is None:
            return False

        try:
            current_content = self.storage.read(self._filename)
            return current_content.strip() == self._last_saved_content
        except Exception as e:
            LOGGER.debug(
                f"Error reading file to check if content matches: {e}"
            )
            return False


def read_css_file(css_file: str, filename: str | None) -> str | None:
    """Read the contents of a CSS file.

    Args:
        css_file: The path to the CSS file.
        filename: The filename of the notebook.

    Returns:
        The contents of the CSS file.
    """
    if not css_file:
        return None

    filepath = Path(css_file)

    # If not an absolute path, make it absolute using the filename
    if not filepath.is_absolute():
        if not filename:
            return None
        filepath = Path(filename).parent / filepath

    if not filepath.exists():
        LOGGER.error("CSS file %s does not exist", filepath)
        return None
    try:
        return filepath.read_text(encoding="utf-8")
    except OSError as e:
        LOGGER.warning(
            "Failed to open custom CSS file %s for reading: %s",
            filepath,
            str(e),
        )
        return None


def read_html_head_file(
    html_head_file: str, filename: str | None
) -> str | None:
    """Read the contents of an HTML head file.

    Args:
        html_head_file: The path to the HTML head file.
        filename: The filename of the notebook.

    Returns:
        The contents of the HTML head file.
    """
    if not html_head_file or not filename:
        return None

    app_dir = Path(filename).parent
    filepath = app_dir / html_head_file
    if not filepath.exists():
        LOGGER.error("HTML head file %s does not exist", html_head_file)
        return None
    try:
        return filepath.read_text(encoding="utf-8")
    except OSError as e:
        LOGGER.warning(
            "Failed to open HTML head file %s for reading: %s",
            filepath,
            str(e),
        )
        return None


def _maybe_path(path: str | Path | None) -> Path | None:
    """Convert a string or Path to a Path object."""
    if path is None:
        return None
    if isinstance(path, Path):
        return path
    return Path(path)


def _build_transaction(
    *, prev: CellManager, new: CellManager
) -> tuple[Transaction, set[CellId_t]]:
    """Diff two CellManagers, returning ``(transaction, changed_cell_ids)``.

    The transaction is unstamped; the caller applies it to the document
    (which assigns ``version``). ``changed_cell_ids`` covers code, name,
    or config changes plus all creates and deletes — reorder-only cells
    are excluded.
    """
    prev_data = {cd.cell_id: cd for cd in prev.cell_data()}
    prev_cell_ids = list(prev.cell_ids())
    new_cell_ids = list(new.cell_ids())
    deleted = set(prev_data) - set(new_cell_ids)

    changes: list[DocumentChange] = []
    changed_cell_ids: set[CellId_t] = set(deleted)
    for cid in deleted:
        changes.append(DeleteCell(cell_id=cid))

    for cd in new.cell_data():
        prev_cd = prev_data.get(cd.cell_id)
        if prev_cd is None:
            changes.append(
                CreateCell(
                    cell_id=cd.cell_id,
                    code=cd.code,
                    name=cd.name,
                    config=cd.config,
                )
            )
            changed_cell_ids.add(cd.cell_id)
            continue
        if cd.code != prev_cd.code:
            changes.append(SetCode(cell_id=cd.cell_id, code=cd.code))
            changed_cell_ids.add(cd.cell_id)
        if cd.name != prev_cd.name:
            changes.append(SetName(cell_id=cd.cell_id, name=cd.name))
            changed_cell_ids.add(cd.cell_id)
        if cd.config != prev_cd.config:
            changes.append(
                SetConfig(
                    cell_id=cd.cell_id,
                    column=cd.config.column,
                    disabled=cd.config.disabled,
                    hide_code=cd.config.hide_code,
                )
            )
            changed_cell_ids.add(cd.cell_id)

    if tuple(new_cell_ids) != tuple(prev_cell_ids):
        changes.append(ReorderCells(cell_ids=tuple(new_cell_ids)))

    return (
        Transaction(changes=tuple(changes), source="file-watch"),
        changed_cell_ids,
    )
