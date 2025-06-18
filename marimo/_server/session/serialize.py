# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Union, cast

from marimo import __version__, _loggers
from marimo._ast.cell_manager import CellManager
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    Error as MarimoError,
    MarimoExceptionRaisedError,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.ops import CellOp
from marimo._schemas.notebook import (
    NotebookCell,
    NotebookCellConfig,
    NotebookMetadata,
    NotebookV1,
)
from marimo._schemas.session import (
    VERSION,
    Cell,
    DataOutput,
    ErrorOutput,
    NotebookSessionMetadata,
    NotebookSessionV1,
    OutputType,
    StreamOutput,
)
from marimo._server.session.session_view import SessionView
from marimo._types.ids import CellId_t
from marimo._utils.background_task import AsyncBackgroundTask
from marimo._utils.lists import as_list

LOGGER = _loggers.marimo_logger()


def _normalize_error(error: Union[MarimoError, dict[str, Any]]) -> ErrorOutput:
    """Normalize error to consistent format."""
    if isinstance(error, dict):
        return ErrorOutput(
            type="error",
            ename=error.get("type", "UnknownError"),
            evalue=error.get("msg", ""),
            traceback=error.get("traceback", []),
        )
    else:
        return ErrorOutput(
            type="error",
            ename=error.type,
            evalue=error.describe(),
            traceback=getattr(error, "traceback", []),
        )


def serialize_session_view(view: SessionView) -> NotebookSessionV1:
    """Convert a SessionView to a NotebookSession schema."""
    cells: list[Cell] = []

    for cell_id, cell_op in view.cell_operations.items():
        outputs: list[OutputType] = []
        console: list[StreamOutput] = []

        # Convert output
        if cell_op.output:
            if cell_op.output.channel == CellChannel.MARIMO_ERROR:
                for error in cast(
                    list[Union[MarimoError, dict[str, Any]]],
                    cell_op.output.data,
                ):
                    outputs.append(_normalize_error(error))
            else:
                outputs.append(
                    DataOutput(
                        type="data",
                        data={
                            cell_op.output.mimetype: cell_op.output.data,
                        },
                    )
                )

        # Convert console outputs
        for console_out in as_list(cell_op.console):
            assert isinstance(console_out, CellOutput)
            if console_out:
                console.append(
                    StreamOutput(
                        type="stream",
                        name="stderr"
                        if console_out.channel == CellChannel.STDERR
                        else "stdout",
                        text=str(console_out.data),
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
        metadata=NotebookSessionMetadata(marimo_version=__version__),
        cells=cells,
    )


def deserialize_session(session: NotebookSessionV1) -> SessionView:
    """Convert a NotebookSession schema to a SessionView."""
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
                                type="exception",
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
            console_outputs.append(
                CellOutput(
                    channel=CellChannel.STDERR
                    if console["name"] == "stderr"
                    else CellChannel.STDOUT,
                    data=console["text"],
                    mimetype="text/plain",
                )
            )

        cell_id = CellId_t(cell["id"])

        view.cell_operations[cell_id] = CellOp(
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

    for cell_id in view.cell_operations.keys():
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
            )
        else:
            name = cell_data.name
            config = NotebookCellConfig(
                column=cell_data.config.column,
                disabled=cell_data.config.disabled,
                hide_code=cell_data.config.hide_code,
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
    return path.parent / "__marimo__" / "session" / f"{path.name}.json"


def _hash_code(code: Optional[str]) -> Optional[str]:
    if code is None or code == "":
        return None
    return hashlib.md5(code.encode("utf-8"), usedforsecurity=False).hexdigest()


class SessionCacheWriter(AsyncBackgroundTask):
    """Periodically writes a SessionView to a file."""

    def __init__(
        self,
        session_view: SessionView,
        path: Path,
        interval: float,
    ) -> None:
        super().__init__()
        self.session_view = session_view
        self.path = path
        self.interval = interval

    async def startup(self) -> None:
        # Create parent directories if they don't exist
        try:
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
                    data = serialize_session_view(self.session_view)
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


class SessionCacheManager:
    """Manages the session cache writer.

    Handles renaming the file and when the file is not named.
    """

    def __init__(
        self,
        session_view: SessionView,
        path: Optional[str | Path],
        interval: float,
    ):
        self.session_view = session_view
        self.path = path
        self.interval = interval
        self.session_cache_writer: SessionCacheWriter | None = None

    def start(self) -> None:
        """Start the session cache writer"""
        if self.path is None:
            return

        cache_file = get_session_cache_file(Path(self.path))

        self.session_cache_writer = SessionCacheWriter(
            session_view=self.session_view,
            path=cache_file,
            interval=self.interval,
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
        if (len(key.codes) != len(notebook_session["cells"])) or any(
            _hash_code(code) != cell["code_hash"]
            for code, cell in zip(key.codes, notebook_session["cells"])
        ):
            return False
        if (
            key.marimo_version
            != notebook_session["metadata"]["marimo_version"]
        ):
            return False
        return True

    def read_session_view(self, key: SessionCacheKey) -> SessionView:
        """Read the session view from the cache files.

        Mutates the session view on cache hit.
        """
        if self.path is None:
            return self.session_view
        cache_file = get_session_cache_file(Path(self.path))
        if not cache_file.exists():
            return self.session_view
        notebook_session: NotebookSessionV1 = json.loads(
            cache_file.read_text()
        )
        if not self.is_cache_hit(notebook_session, key):
            LOGGER.debug("Session view cache miss")
            return self.session_view

        self.session_view = deserialize_session(
            json.loads(cache_file.read_text())
        )
        return self.session_view
