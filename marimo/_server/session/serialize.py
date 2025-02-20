# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import List, Optional, cast

from marimo import __version__, _loggers
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.errors import (
    Error as MarimoError,
    MarimoExceptionRaisedError,
)
from marimo._messaging.mimetypes import KnownMimeType
from marimo._messaging.ops import CellOp
from marimo._schemas.session import (
    VERSION,
    Cell,
    DataOutput,
    ErrorOutput,
    NotebookMetadata,
    NotebookSessionV1,
    OutputType,
    StreamOutput,
)
from marimo._server.session.session_view import SessionView
from marimo._types.ids import CellId_t
from marimo._utils.background_task import AsyncBackgroundTask
from marimo._utils.lists import as_list

LOGGER = _loggers.marimo_logger()


def serialize_session_view(view: SessionView) -> NotebookSessionV1:
    """Convert a SessionView to a NotebookSession schema."""
    cells: List[Cell] = []

    for cell_id, cell_op in view.cell_operations.items():
        outputs: List[OutputType] = []
        console: List[StreamOutput] = []

        # Convert output
        if cell_op.output:
            if cell_op.output.channel == CellChannel.MARIMO_ERROR:
                for error in cast(List[MarimoError], cell_op.output.data):
                    outputs.append(
                        ErrorOutput(
                            type="error",
                            ename=error.type,
                            evalue=error.describe(),
                            traceback=[],
                        )
                    )
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
        metadata=NotebookMetadata(marimo_version=__version__),
        cells=cells,
    )


def deserialize_session(session: NotebookSessionV1) -> SessionView:
    """Convert a NotebookSession schema to a SessionView."""
    view = SessionView()

    for cell in session["cells"]:
        cell_outputs: List[CellOutput] = []

        # Convert outputs
        for output in cell["outputs"]:
            if output["type"] == "error":
                cell_outputs.append(
                    CellOutput(
                        channel=CellChannel.MARIMO_ERROR,
                        mimetype="text/plain",
                        data=[
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
        console_outputs: List[CellOutput] = []
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

    def read_session_view(self) -> SessionView:
        """Read the session view from the cache file"""
        if self.path is None:
            return self.session_view
        cache_file = get_session_cache_file(Path(self.path))
        if not cache_file.exists():
            return self.session_view
        self.session_view = deserialize_session(
            json.loads(cache_file.read_text())
        )
        return self.session_view
