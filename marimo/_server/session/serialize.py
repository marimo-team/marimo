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
    NotebookSession,
    OutputType,
    StreamOutput,
)
from marimo._server.session.session_view import SessionView
from marimo._utils.lists import as_list

LOGGER = _loggers.marimo_logger()


def serialize_session_view(view: SessionView) -> NotebookSession:
    """Convert a SessionView to a NotebookSession schema."""
    cells: List[Cell] = []

    for cell_id, cell_op in view.cell_operations.items():
        outputs: List[OutputType] = []
        console: List[StreamOutput] = []

        # Convert output
        if cell_op.output:
            if cell_op.output.channel == CellChannel.MARIMO_ERROR:
                for error in cast(List[MarimoError], cell_op.output.data):
                    assert isinstance(error, MarimoError)
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

    return NotebookSession(
        version=VERSION,
        metadata=NotebookMetadata(marimo_version=__version__),
        cells=cells,
    )


def deserialize_session(session: NotebookSession) -> SessionView:
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

        view.cell_operations[cell["id"]] = CellOp(
            cell_id=cell["id"],
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


class SessionCacheWriter:
    """Periodically writes a SessionView to a file."""

    def __init__(
        self,
        session_view: SessionView,
        path: Path,
        interval: float,
    ):
        self.session_view = session_view
        self.path = path
        self.interval = interval
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def _write_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                has_made_dirs = False
                try:
                    if self.session_view.needs_export("session"):
                        LOGGER.debug("Writing session view to cache")
                        try:
                            data = serialize_session_view(self.session_view)
                            # Create parent directories if they don't exist
                            if not has_made_dirs:
                                self.path.parent.mkdir(
                                    parents=True, exist_ok=True
                                )
                                has_made_dirs = True
                            self.path.write_text(json.dumps(data))
                        except Exception as e:
                            LOGGER.error(f"Write error: {e}")
                            # If we fail to write, we should stop the writer
                            break
                    await asyncio.sleep(self.interval)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    LOGGER.error(f"Write error: {e}")
        finally:
            self._task = None
            self._stop_event.clear()

    def start(self) -> None:
        """Start the periodic writer"""
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._write_loop())
        else:
            LOGGER.warning("AsyncWriter already running")

    def stop(self) -> None:
        """Stop the periodic writer synchronously"""
        if self._task is not None:
            self._stop_event.set()
            self._task.cancel()
            try:
                # Create a future to track when the task is done
                done: asyncio.Future[bool] = asyncio.Future()
                # Only set the callback, don't set the result first
                self._task.add_done_callback(lambda _: done.set_result(True))
            except asyncio.CancelledError:
                pass
            self._task = None
        else:
            LOGGER.warning("AsyncWriter not running")


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
        self.session_cache_writer.stop()
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
