# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from marimo import _loggers
from marimo._ast.cell_manager import CellManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    Error as MarimoError,
    MarimoExceptionRaisedError,
    UnknownError,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.msgspec_encoder import asdict
from marimo._messaging.notebook.document import NotebookDocument
from marimo._messaging.notification import CellNotification
from marimo._schemas.notebook import (
    NotebookCell,
    NotebookCellConfig,
    NotebookMetadata,
    NotebookV1,
)
from marimo._schemas.session import (
    VERSION,
    Cell,
    ConsoleType,
    DataOutput,
    ErrorOutput,
    NotebookSessionMetadata,
    NotebookSessionV1,
    OutputType,
    StreamMediaOutput,
    StreamOutput,
)
from marimo._session.state.session_view import SessionView
from marimo._types.ids import CellId_t
from marimo._utils.async_path import AsyncPath
from marimo._utils.background_task import AsyncBackgroundTask
from marimo._utils.code import hash_code
from marimo._utils.lists import as_list
from marimo._version import __version__

if TYPE_CHECKING:
    from collections.abc import Iterable

LOGGER = _loggers.marimo_logger()


# Matches the runtime's virtual-file URL shape: `./@file/<bytes>-<name>`
# (see `marimo/_runtime/virtual_file/virtual_file.py`). Anchored to the
# byte-length digits so a literal "./@file/" mention in user content
# doesn't trip the check.
_VIRTUAL_FILE_URL_RE = re.compile(r"\./@file/\d+-")


def _references_virtual_file(data: Any) -> bool:
    """Return True if `data` references a virtual-file URL.

    Virtual files (`./@file/<bytes>-<name>`) are backed by per-process
    storage that disappears on kernel restart, so any cached output that
    embeds one would 404 on replay (e.g. anywidget HTML losing its binary
    state — see #9273).
    """
    return _references_virtual_file_inner(data, set())


def _references_virtual_file_inner(data: Any, seen: set[int]) -> bool:
    if isinstance(data, str):
        return _VIRTUAL_FILE_URL_RE.search(data) is not None
    if isinstance(data, (dict, list)):
        # Guard against cycles: session outputs shouldn't contain them in
        # practice, but a self-referencing structure should return False
        # cleanly rather than blow the stack.
        container_id = id(data)
        if container_id in seen:
            return False
        seen.add(container_id)
        if isinstance(data, dict):
            return any(
                _references_virtual_file_inner(v, seen) for v in data.values()
            )
        return any(_references_virtual_file_inner(v, seen) for v in data)
    return False


def _normalize_error(error: MarimoError | dict[str, Any]) -> ErrorOutput:
    """Normalize error to consistent format."""
    if isinstance(error, dict):
        return ErrorOutput(
            type="error",
            ename=error.get("type", "UnknownError"),
            evalue=error.get("msg", ""),
            traceback=error.get("traceback", []),
        )
    else:
        if isinstance(error, UnknownError) and error.error_type:
            # UnknownError with custom error_type field
            ename = error.error_type
        else:
            # For msgspec structs with tagged unions, the type is in the serialized form
            ename = asdict(error).get("type", "UnknownError")

        return ErrorOutput(
            type="error",
            ename=ename,
            evalue=error.describe(),
            traceback=getattr(error, "traceback", []),
        )


def serialize_session_view(
    view: SessionView,
    cell_ids: Iterable[CellId_t],
    *,
    drop_virtual_file_outputs: bool,
    script_metadata_hash: str | None = None,
) -> NotebookSessionV1:
    """Convert a SessionView to a NotebookSession schema.

    When `cell_ids` is provided, it determines the order of the cells in
    the NotebookSession schema (and only these cells will be saved to the
    schema). When not provided, this method attempts to recover the notebook
    order from the SessionView object, but this is not always possible.

    `./@file/...` URLs are backed by per-process buffers, so
    `drop_virtual_file_outputs` depends on where the snapshot will be
    consumed:

    - `True` when the snapshot will be replayed in a *different*
      process from the one that produced it. The buffers are gone, so
      surviving URLs would 404 on replay (#9273); dropping them leaves
      the cell un-run until the kernel re-executes it. Used by the
      on-disk session cache.
    - `False` when the snapshot will be consumed in the *same* process
      while buffers are still live, and the caller resolves the URLs
      itself before they're released — e.g. HTML export inlining them
      as `data:` URLs.
    """
    cells: list[Cell] = []

    for cell_id in cell_ids:
        cell_notif = view.cell_notifications.get(cell_id)
        if cell_notif is None:
            # We haven't seen any outputs or notifications for this cell.
            cells.append(
                Cell(id=cell_id, code_hash=None, outputs=[], console=[])
            )
            continue
        outputs: list[OutputType] = []
        console: list[ConsoleType] = []

        # Convert output
        if cell_notif.output:
            if cell_notif.output.channel == CellChannel.MARIMO_ERROR:
                for error in cast(
                    list[MarimoError | dict[str, Any]],
                    cell_notif.output.data,
                ):
                    outputs.append(_normalize_error(error))
            elif not (
                drop_virtual_file_outputs
                and _references_virtual_file(cell_notif.output.data)
            ):
                outputs.append(
                    DataOutput(
                        type="data",
                        data={
                            cell_notif.output.mimetype: cell_notif.output.data,
                        },
                    )
                )

        # Convert console outputs
        for console_out in as_list(cell_notif.console):
            assert isinstance(console_out, CellOutput)
            if console_out.channel == CellChannel.MEDIA:
                console.append(
                    StreamMediaOutput(
                        type="streamMedia",
                        name="media",
                        mimetype=console_out.mimetype,
                        data=str(console_out.data),
                    )
                )
            else:
                # catch all for everything else
                console.append(
                    StreamOutput(
                        type="stream",
                        name="stderr"
                        if console_out.channel == CellChannel.STDERR
                        else "stdout",
                        text=str(console_out.data),
                        mimetype=console_out.mimetype,
                    )
                )

        code_hash = _hash_code(view.last_executed_code.get(cell_id))

        cells.append(
            Cell(
                id=cell_id,
                code_hash=code_hash,
                outputs=outputs,
                console=console,
            )
        )

    return NotebookSessionV1(
        version=VERSION,
        metadata=NotebookSessionMetadata(
            marimo_version=__version__,
            script_metadata_hash=script_metadata_hash,
        ),
        cells=cells,
    )


def deserialize_session(
    session: NotebookSessionV1,
    code_hash_to_cell_id: dict[str, CellId_t],
) -> SessionView:
    """Convert a NotebookSession schema to a SessionView.

    Args:
        session: The serialized notebook session
        code_hash_to_cell_id: Mapping from code hash to current cell ID.
            Cells are matched by code hash instead of using the stored cell_id,
            which handles cases where cells were added/deleted.
    """
    view = SessionView()

    for cell in session["cells"]:
        cell_outputs: list[CellOutput] = []

        # Convert outputs
        for output in cell["outputs"]:
            if output["type"] == "error":
                cell_outputs.append(
                    CellOutput.errors(
                        [
                            MarimoExceptionRaisedError(
                                exception_type=output["ename"],
                                msg=output["evalue"],
                                raising_cell=None,
                            )
                        ],
                    )
                )
            elif output["type"] == "data":
                # No data
                if len(output["data"]) == 0:
                    continue
                elif len(output["data"]) == 1:
                    cell_outputs.append(
                        CellOutput(
                            channel=CellChannel.OUTPUT,
                            mimetype=cast(
                                KnownMimeType,
                                next(iter(output["data"].keys())),
                            ),
                            data=next(iter(output["data"].values())),
                        )
                    )
                else:
                    # Mime bundle
                    cell_outputs.append(
                        CellOutput(
                            channel=CellChannel.OUTPUT,
                            mimetype="application/vnd.marimo+mimebundle",
                            data=output["data"],
                        )
                    )
            else:
                LOGGER.warning(f"Unknown output type: {output}")
                continue

        # Convert console
        console_outputs: list[CellOutput] = []
        for console in cell["console"]:
            if console["name"] == "media":
                console_outputs.append(
                    CellOutput(
                        channel=CellChannel.MEDIA,
                        data=console["data"],
                        mimetype=console["mimetype"],
                    )
                )
            else:
                is_stderr = console["name"] == "stderr"
                data = console["text"]

                # Use mimetype from console if available (new format)
                if "mimetype" in console and console["mimetype"] is not None:
                    mimetype = console["mimetype"]
                else:
                    # Backward compatibility: detect mimetype using heuristics
                    # HACK: We need to detect tracebacks in stderr by checking for HTML
                    # formatting.
                    is_traceback = (
                        is_stderr
                        and isinstance(data, str)
                        and data.startswith('<span class="codehilite">')
                    )
                    mimetype = cast(
                        KnownMimeType,
                        "application/vnd.marimo+traceback"
                        if is_traceback
                        else "text/plain",
                    )

                console_outputs.append(
                    CellOutput(
                        channel=CellChannel.STDERR
                        if is_stderr
                        else CellChannel.STDOUT,
                        data=data,
                        mimetype=mimetype,
                    )
                )

        # Match cell by code_hash
        if cell["code_hash"] is None:
            # No code hash available - skip this cell
            LOGGER.debug(
                f"Skipping cached output for cell {cell['id']} - no code_hash"
            )
            continue

        cell_id = code_hash_to_cell_id.get(cell["code_hash"])
        if cell_id is None:
            # No matching cell found by code hash - skip this cell
            LOGGER.debug(
                f"Skipping cached output for cell with hash "
                f"{cell['code_hash'][:8]}... - no matching cell found"
            )
            continue

        view.cell_notifications[cell_id] = CellNotification(
            cell_id=cell_id,
            status="idle",
            output=cell_outputs[0] if cell_outputs else None,
            console=console_outputs,
            timestamp=0,
        )

    return view


def serialize_notebook(
    view: SessionView, cell_manager: CellManager
) -> NotebookV1:
    """Convert a SessionView to a Notebook schema."""
    cells: list[NotebookCell] = []

    # Use document order from cell_manager instead of execution order from session_view
    # to ensure cells appear in the correct sequence in HTML export
    for cell_id in cell_manager.cell_ids():
        # Get the code from last_executed_code, fallback to empty string
        code = view.last_executed_code.get(cell_id, "")
        cell_data = cell_manager.get_cell_data(cell_id)
        if cell_data is None:
            LOGGER.warning(f"Cell data not found for cell {cell_id}")
            name = None
            config = NotebookCellConfig(
                column=None,
                disabled=None,
                hide_code=None,
                expand_output=None,
            )
        else:
            name = cell_data.name
            config = NotebookCellConfig(
                column=cell_data.config.column,
                disabled=cell_data.config.disabled,
                hide_code=cell_data.config.hide_code,
                expand_output=cell_data.config.expand_output,
            )

        cells.append(
            NotebookCell(
                id=cell_id,
                code=code,
                code_hash=_hash_code(code),
                name=name,
                config=config,
            )
        )

    return NotebookV1(
        version="1",
        metadata=NotebookMetadata(marimo_version=__version__),
        cells=cells,
    )


def get_session_cache_file(path: Path) -> Path:
    """Get the cache file for a given path.

    For example, if the path is `foo/bar/baz.py`, the cache file is
    `foo/bar/__marimo__/session/baz.py.json`.
    """
    from marimo._utils.paths import notebook_output_dir

    return notebook_output_dir(path) / "session" / f"{path.name}.json"


def _hash_code(code: str | None) -> str | None:
    if code is None or code == "":
        return None
    return hash_code(code)


def _script_metadata_hash(path: Path | str | None) -> str | None:
    if path is None:
        return None
    from marimo._utils.inline_script_metadata import (
        script_metadata_hash_from_filename,
    )

    return script_metadata_hash_from_filename(str(path))


class SessionCacheWriter(AsyncBackgroundTask):
    """Periodically writes a SessionView to a file."""

    def __init__(
        self,
        session_view: SessionView,
        document: NotebookDocument,
        path: Path,
        interval: float,
        notebook_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.session_view = session_view
        self.document = document
        self.notebook_path = notebook_path
        # Windows does not support our async path implementation
        self.path: AsyncPath | Path = path
        if os.name != "nt":
            self.path = AsyncPath(path)
        self.interval = interval

    async def startup(self) -> None:
        # Create parent directories if they don't exist
        try:
            if isinstance(self.path, AsyncPath):
                await self.path.parent.mkdir(parents=True, exist_ok=True)
            else:
                self.path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            LOGGER.error(f"Failed to create parent directories: {e}")
            raise

    async def run(self) -> None:
        while self.running:
            try:
                if self.session_view.needs_export("session"):
                    self.session_view.mark_auto_export_session()
                    LOGGER.debug(f"Writing session view to cache {self.path}")
                    data = serialize_session_view(
                        self.session_view,
                        cell_ids=self.document.cell_ids,
                        script_metadata_hash=_script_metadata_hash(
                            self.notebook_path
                        ),
                        drop_virtual_file_outputs=True,
                    )
                    if isinstance(self.path, AsyncPath):
                        await self.path.write_text(json.dumps(data, indent=2))
                    else:
                        self.path.write_text(json.dumps(data, indent=2))
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                LOGGER.error(f"Write error: {e}")
                # If we fail to write, we should stop the writer
                break


@dataclass
class SessionCacheKey:
    codes: tuple[str | None, ...]
    marimo_version: str
    cell_ids: tuple[CellId_t, ...]
    script_metadata_hash: str | None = None


class SessionCacheManager:
    """Manages the session cache writer.

    Handles renaming the file and when the file is not named.
    """

    def __init__(
        self,
        session_view: SessionView,
        document: NotebookDocument,
        path: str | Path | None,
        interval: float,
    ):
        self.session_view = session_view
        self.document = document
        self.path = path
        self.interval = interval
        self.session_cache_writer: SessionCacheWriter | None = None

    def start(self) -> None:
        """Start the session cache writer"""
        if self.path is None:
            return

        notebook_path = Path(self.path)
        cache_file = get_session_cache_file(notebook_path)

        self.session_cache_writer = SessionCacheWriter(
            session_view=self.session_view,
            document=self.document,
            path=cache_file,
            interval=self.interval,
            notebook_path=notebook_path,
        )
        self.session_cache_writer.start()

    def stop(self) -> bool:
        """Stop the session cache writer. Returns whether it was running."""
        if self.session_cache_writer is None:
            return False
        self.session_cache_writer.stop_sync()
        self.session_cache_writer = None
        return True

    def rename_path(self, new_path: str | Path) -> None:
        """Rename the path to the new path"""
        self.stop()
        self.path = new_path
        self.start()

    def is_cache_hit(
        self, notebook_session: NotebookSessionV1, key: SessionCacheKey
    ) -> bool:
        metadata = notebook_session.get("metadata")
        if not isinstance(metadata, dict):
            return False
        if (len(key.codes) != len(notebook_session["cells"])) or any(
            _hash_code(code) != cell["code_hash"]
            for code, cell in zip(
                key.codes, notebook_session["cells"], strict=False
            )
        ):
            return False
        if key.marimo_version != metadata.get("marimo_version"):
            return False
        if "script_metadata_hash" not in metadata:
            return False
        return metadata.get("script_metadata_hash") == key.script_metadata_hash

    def read_session_view(self, key: SessionCacheKey) -> SessionView:
        """Read the session view from the cache files.

        Mutates the session view on cache hit.
        """
        if self.path is None:
            return self.session_view
        cache_file = get_session_cache_file(Path(self.path))
        if not cache_file.exists():
            return self.session_view
        try:
            notebook_session: NotebookSessionV1 = json.loads(
                cache_file.read_text()
            )
        except Exception as e:
            LOGGER.error(f"Failed to read session cache file: {e}")
            return self.session_view

        if not self.is_cache_hit(notebook_session, key):
            LOGGER.info("Session view cache miss")
            return self.session_view

        # Build mapping from code_hash to cell_id based on current cell IDs
        # This handles cases where cell_ids have changed even though code matches
        code_hash_to_cell_id: dict[str, CellId_t] = {}
        for code, cell_id in zip(key.codes, key.cell_ids, strict=False):
            code_hash = _hash_code(code)
            if code_hash is not None:
                # Map the code_hash to the current cell_id from the key
                code_hash_to_cell_id[code_hash] = cell_id

        self.session_view = deserialize_session(
            notebook_session, code_hash_to_cell_id
        )
        return self.session_view
