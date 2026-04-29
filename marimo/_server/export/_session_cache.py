# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from marimo._session.notebook import load_notebook
from marimo._session.state.serialize import (
    get_session_cache_file,
    serialize_session_view,
)
from marimo._utils.code import hash_code
from marimo._utils.inline_script_metadata import (
    script_metadata_hash_from_filename,
)
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import maybe_make_dirs

if TYPE_CHECKING:
    from collections.abc import Iterable

    from marimo._schemas.session import NotebookSessionV1
    from marimo._session.state.session_view import SessionView
    from marimo._types.ids import CellId_t


def get_script_metadata_hash(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return script_metadata_hash_from_filename(str(path))


def _hash_code_for_session_compare(code: str | None) -> str | None:
    if code is None or code == "":
        return None
    return hash_code(code)


def current_notebook_code_hashes(
    notebook: MarimoPath,
) -> tuple[str | None, ...]:
    file_manager = load_notebook(notebook.absolute_name)
    return tuple(
        _hash_code_for_session_compare(cell_data.code)
        for cell_data in file_manager.app.cell_manager.cell_data()
    )


def serialize_session_snapshot(
    view: SessionView,
    *,
    notebook_path: str | Path | None,
    cell_ids: Iterable[CellId_t],
) -> NotebookSessionV1:
    return serialize_session_view(
        view,
        cell_ids=cell_ids,
        script_metadata_hash=get_script_metadata_hash(notebook_path),
        drop_virtual_file_outputs=True,
    )


def write_session_snapshot(
    *,
    notebook_path: str | Path,
    snapshot: NotebookSessionV1,
) -> Path:
    output = get_session_cache_file(Path(notebook_path))
    maybe_make_dirs(output)
    output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return output


def persist_session_view_to_cache(
    *,
    view: SessionView,
    notebook_path: str | Path | None,
    cell_ids: Iterable[CellId_t],
) -> Path | None:
    if notebook_path is None:
        return None
    snapshot = serialize_session_snapshot(
        view,
        notebook_path=notebook_path,
        cell_ids=cell_ids,
    )
    return write_session_snapshot(
        notebook_path=notebook_path, snapshot=snapshot
    )


def is_session_snapshot_stale(output: Path, notebook: MarimoPath) -> bool:
    """Return True when a saved session should be regenerated.

    A snapshot is stale if it is unreadable, malformed, missing the
    script metadata hash, or if either the current code-hash multiset or the
    current script metadata hash differs from the snapshot.
    """
    try:
        snapshot = cast(
            dict[str, Any], json.loads(output.read_text(encoding="utf-8"))
        )
    except (OSError, json.JSONDecodeError):
        return True

    metadata = snapshot.get("metadata")
    if not isinstance(metadata, dict):
        return True
    if "script_metadata_hash" not in metadata:
        return True

    session_script_hash = metadata["script_metadata_hash"]
    if session_script_hash is not None and not isinstance(
        session_script_hash, str
    ):
        return True
    if session_script_hash != get_script_metadata_hash(notebook.absolute_name):
        return True

    cells = snapshot.get("cells")
    if not isinstance(cells, list):
        return True

    try:
        current_hashes = current_notebook_code_hashes(notebook)
    except (RuntimeError, ValueError, OSError, SyntaxError):
        return True

    notebook_hashes = Counter(current_hashes)

    session_hashes: Counter[str | None] = Counter()
    for cell in cells:
        if not isinstance(cell, dict):
            return True
        if "code_hash" not in cell:
            return True
        code_hash = cell["code_hash"]
        if code_hash is not None and not isinstance(code_hash, str):
            return True
        session_hashes[code_hash] += 1

    return notebook_hashes != session_hashes
