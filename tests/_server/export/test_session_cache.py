from __future__ import annotations

import json
from typing import Any, cast
from unittest.mock import patch

from marimo._server.export import _session_cache
from marimo._session.state.session_view import SessionView
from marimo._utils.marimo_path import MarimoPath
from marimo._version import __version__


def _write_snapshot(path: str, payload: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload))


def _make_snapshot(
    *,
    code_hashes: list[str | None],
    script_metadata_hash: str | None = "meta-hash",
) -> dict[str, object]:
    metadata: dict[str, str | None] = {"marimo_version": __version__}
    if script_metadata_hash is not None:
        metadata["script_metadata_hash"] = script_metadata_hash
    return {
        "version": "1",
        "metadata": metadata,
        "cells": [
            {"code_hash": code_hash, "outputs": []}
            for code_hash in code_hashes
        ],
    }


def test_is_session_snapshot_stale_false_when_snapshot_is_current(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(code_hashes=["hash-b", "hash-a", None, "hash-a"])
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            return_value=("hash-a", None, "hash-a", "hash-b"),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value="meta-hash",
        ),
    ):
        assert (
            _session_cache.is_session_snapshot_stale(output, notebook) is False
        )


def test_is_session_snapshot_stale_true_when_script_metadata_hash_missing(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(
        code_hashes=["hash-a"],
        script_metadata_hash=None,
    )
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            return_value=("hash-a",),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value=None,
        ),
    ):
        assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_is_session_snapshot_stale_true_when_script_metadata_hash_mismatch(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(
        code_hashes=["hash-a"],
        script_metadata_hash="old",
    )
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            return_value=("hash-a",),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value="new",
        ),
    ):
        assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_is_session_snapshot_stale_true_when_code_hashes_do_not_match(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(code_hashes=["hash-a", "hash-b"])
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            return_value=("hash-a",),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value="meta-hash",
        ),
    ):
        assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_is_session_snapshot_stale_true_when_hash_multiplicity_differs(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(code_hashes=["hash-a"])
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            return_value=("hash-a", "hash-a"),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value="meta-hash",
        ),
    ):
        assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_is_session_snapshot_stale_true_when_cell_missing_code_hash(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(code_hashes=["hash-a"])
    snapshot["cells"] = [{"outputs": []}]
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            return_value=("hash-a",),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value="meta-hash",
        ),
    ):
        assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_is_session_snapshot_stale_true_when_code_hash_has_wrong_type(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(code_hashes=["hash-a"])
    snapshot["cells"] = [{"code_hash": 1, "outputs": []}]
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            return_value=("hash-a",),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value="meta-hash",
        ),
    ):
        assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_is_session_snapshot_stale_true_when_snapshot_is_unreadable(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    output.write_text("{ not valid json", encoding="utf-8")
    notebook = MarimoPath(str(tmp_path / "notebook.py"))
    assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_is_session_snapshot_stale_true_when_hash_lookup_fails(
    tmp_path,
) -> None:
    output = tmp_path / "session.json"
    snapshot = _make_snapshot(code_hashes=["hash-a"])
    _write_snapshot(str(output), snapshot)
    notebook = MarimoPath(str(tmp_path / "notebook.py"))

    with (
        patch.object(
            _session_cache,
            "current_notebook_code_hashes",
            side_effect=RuntimeError("failed to inspect notebook"),
        ),
        patch.object(
            _session_cache,
            "get_script_metadata_hash",
            return_value="meta-hash",
        ),
    ):
        assert _session_cache.is_session_snapshot_stale(output, notebook)


def test_serialize_session_snapshot_includes_script_metadata_hash() -> None:
    view = SessionView()
    with patch.object(
        _session_cache,
        "get_script_metadata_hash",
        return_value="meta-hash",
    ):
        snapshot = _session_cache.serialize_session_snapshot(
            view,
            notebook_path="notebook.py",
            cell_ids=(),
        )

    metadata = snapshot["metadata"]
    assert metadata["script_metadata_hash"] == "meta-hash"


def test_persist_session_view_to_cache_writes_under_marimo_dir(
    tmp_path,
) -> None:
    notebook = tmp_path / "notebook.py"
    notebook.write_text("import marimo\n", encoding="utf-8")

    view = SessionView()
    with patch.object(
        _session_cache,
        "get_script_metadata_hash",
        return_value="meta-hash",
    ):
        output = _session_cache.persist_session_view_to_cache(
            view=view,
            notebook_path=notebook,
            cell_ids=(),
        )

    assert output is not None
    assert output == tmp_path / "__marimo__" / "session" / "notebook.py.json"
    data = cast(dict[str, Any], json.loads(output.read_text(encoding="utf-8")))
    assert data["metadata"]["script_metadata_hash"] == "meta-hash"
