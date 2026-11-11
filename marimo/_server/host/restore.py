# Copyright 2026 Marimo. All rights reserved.
"""Executions restored from the outputs a session stored beside a notebook."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._core import protocol
from marimo._core.executions import CellExecution, Executions
from marimo._core.ids import mint
from marimo._messaging.errors import ANCESTOR_RAISED
from marimo._messaging.tracebacks import is_code_highlighting
from marimo._server.host import diagnostics
from marimo._server.host.translate import (
    displayed,
    plain,
    rendered_traceback,
)
from marimo._session.state.serialize import (
    SessionCacheKey,
    SessionCacheManager,
    get_session_cache_file,
    restore_traceback,
)
from marimo._types.ids import CellId_t
from marimo._utils.code import hash_code
from marimo._utils.inline_script_metadata import (
    script_metadata_hash_from_filename,
)
from marimo._version import __version__

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from marimo._core.document import DocumentCell
    from marimo._schemas.session import (
        Cell,
        ConsoleType,
        ErrorOutput,
        NotebookSessionV1,
        OutputType,
    )

LOGGER = _loggers.marimo_logger()

# TODO(MO-7927): The session reads this file into its own view and writes
# it back from there. Both end when the session consumes the notebook,
# which then writes the results it holds.


def restored_executions(
    file: Path, cells: Sequence[DocumentCell]
) -> Executions:
    """Restore the results stored beside the notebook `file`.

    A session writes each cell's last output there. They are restored
    only when every cell's code, the marimo version, and the script's
    dependencies are the ones the outputs came from. A stored output
    records nothing else about what it read, so that match is what makes
    the outputs agree with each other.
    """
    try:
        stored: NotebookSessionV1 = json.loads(
            get_session_cache_file(file).read_text(encoding="utf-8")
        )
        key = SessionCacheKey(
            codes=tuple(cell.code for cell in cells),
            marimo_version=__version__,
            cell_ids=tuple(CellId_t(cell.id) for cell in cells),
            script_metadata_hash=script_metadata_hash_from_filename(str(file)),
        )
        if not SessionCacheManager.is_cache_hit(stored, key):
            return Executions()
        return executions_from_session(stored, cells)
    except FileNotFoundError:
        return Executions()
    except Exception as e:
        LOGGER.warning("Could not restore the results of %s: %s", file, e)
        return Executions()


def executions_from_session(
    session: NotebookSessionV1, cells: Sequence[DocumentCell]
) -> Executions:
    """Restore what a stored session holds for `cells`, as far as it tells.

    Stored cells are taken in the document's order. One whose code hash
    is not its cell's is left out, and so is one with nothing to show.
    A restored execution names no run or runtime, and it has no
    dependencies, variables, or times, because a session stores none.
    """
    results: dict[protocol.CellId, CellExecution] = {}
    for cell, stored in zip(cells, session["cells"], strict=False):
        if stored["code_hash"] != hash_code(cell.code):
            continue
        result = _result(cell, stored)
        if result is not None:
            results[cell.id] = result
    return Executions.restore(results, cells=cells)


def _result(cell: DocumentCell, stored: Cell) -> CellExecution | None:
    execution_id = mint(protocol.ExecutionId, "ex")
    outcome = _outcome(cell, stored["outputs"])
    console = _console(execution_id, stored["console"])
    if outcome == protocol.ValueOutcome(None) and not console:
        return None
    return CellExecution(
        protocol.Execution(
            id=execution_id,
            run_id=None,
            runtime_id=None,
            caused_by=None,
            cell_id=cell.id,
            code=None,
            code_fingerprint=protocol.CodeFingerprint(cell.code_fingerprint),
            depends_on={},
            status="completed",
            outcome=outcome,
            started_at=None,
            completed_at=None,
        ),
        console,
    )


# A session stores a raised exception under its class name and every other
# kernel error under the tag of its type.
_SKIPPED = {
    "ancestor-stopped": "upstream-stopped",
    "ancestor-prevented": "upstream-failed",
    ANCESTOR_RAISED: "upstream-failed",
}
_KINDS = {
    "syntax": "invalid-syntax",
    "cycle": "cycle-dependencies",
    "multiple-defs": "multiple-definitions",
    "setup-refs": "setup-refs",
    "import-star": "import-star",
    "lazy-import": "lazy-import",
    "strict-exception": "strict-exception",
    "sql-error": "sql",
    "internal": "internal",
    "unknown": "internal",
}


def _failure(cell: DocumentCell, stored: ErrorOutput) -> protocol.Outcome:
    """A stored error as the outcome a live run reports for it.

    The file keeps an error's type and message and not the cells it
    named, so a skipped cell names only itself.
    """
    name, message = stored["ename"], stored["evalue"]
    if name == "interruption":
        return protocol.InterruptedOutcome()
    if name in _SKIPPED:
        return protocol.SkippedOutcome(
            reason=_SKIPPED[name],
            message=message.rstrip(": "),
            related=(
                protocol.Related(
                    cell_id=cell.id, range=None, message="Did not run"
                ),
            ),
        )
    traceback = restore_traceback(stored.get("traceback"))
    return protocol.ErrorOutcome(
        diagnostics.error(
            _KINDS.get(name, "exception"),
            message,
            name=None if name in _KINDS else name,
            traceback=None
            if traceback is None
            else displayed(
                "text/html"
                if is_code_highlighting(traceback)
                else "text/plain",
                traceback,
            ),
        )
    )


def _outcome(
    cell: DocumentCell, outputs: Sequence[OutputType]
) -> protocol.Outcome:
    """The first stored output that shows something, as an outcome."""
    for output in outputs:
        if output["type"] == "error":
            return _failure(cell, output)
        if output["type"] == "data" and output["data"]:
            data = output["data"]
            mimetype, value = (
                next(iter(data.items()))
                if len(data) == 1
                else ("application/vnd.marimo+mimebundle", data)
            )
            text = value if isinstance(value, str) else json.dumps(value)
            if (mimetype, text) != ("text/plain", ""):
                return protocol.ValueOutcome(
                    protocol.DisplayData(mimetype=mimetype, data=text)
                )
    return protocol.ValueOutcome(None)


def _console(
    execution_id: protocol.ExecutionId, entries: Sequence[ConsoleType]
) -> tuple[protocol.Console | protocol.Display, ...]:
    """The stored console text and media, in the order they were written."""
    items: list[protocol.Console | protocol.Display] = []
    for entry in entries:
        item_id = protocol.ItemId(f"{execution_id}-{len(items)}")
        if entry["type"] == "streamMedia":
            items.append(
                protocol.Display(
                    id=item_id,
                    execution_id=execution_id,
                    seq=len(items),
                    content=displayed(entry["mimetype"], entry["data"]),
                )
            )
        elif rendered_traceback(entry.get("mimetype"), entry["text"]):
            items.append(
                protocol.Display(
                    id=item_id,
                    execution_id=execution_id,
                    seq=len(items),
                    content=displayed(
                        "application/vnd.marimo+traceback", entry["text"]
                    ),
                )
            )
        # Older files stored a password prompt and its answer as text.
        elif entry.get("mimetype") != "text/password":
            items.append(
                protocol.Console(
                    id=item_id,
                    execution_id=execution_id,
                    seq=len(items),
                    name=entry["name"],
                    text=plain(entry["text"]),
                )
            )
    return tuple(items)
