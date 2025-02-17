from __future__ import annotations

import hashlib
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


def _hash_code(code: Optional[str]) -> Optional[str]:
    if code is None:
        return None
    return hashlib.md5(code.encode("utf-8"), usedforsecurity=False).hexdigest()
