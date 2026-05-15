# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._pyodide.pyodide_constraints import (
    fetch_pyodide_package_versions,
    normalize_package_name,
    write_constraint_file,
)
from marimo._utils.requests import Response

if TYPE_CHECKING:
    from pathlib import Path

_FAKE_LOCKFILE = {
    "packages": {
        "numpy": {
            "name": "numpy",
            "version": "2.0.2",
            "package_type": "package",
        },
        "pandas": {
            "name": "pandas",
            "version": "2.2.3",
            "package_type": "package",
        },
        "numpy-tests": {
            "name": "numpy-tests",
            "version": "2.0.2",
            "package_type": "package",
        },
        "pyodide-runtime": {
            "name": "pyodide-runtime",
            "version": "1.0",
            "package_type": "shared_library",
        },
    }
}


def _fake_response(payload: dict[str, object]) -> Response:
    return Response(
        status_code=200,
        content=json.dumps(payload).encode("utf-8"),
        headers={},
    )


def _patched_get(payload: dict[str, object]):
    return patch(
        "marimo._pyodide.pyodide_constraints.requests.get",
        return_value=_fake_response(payload),
    )


def test_fetch_pyodide_package_versions_filters_test_and_non_package() -> None:
    with _patched_get(_FAKE_LOCKFILE):
        versions = fetch_pyodide_package_versions()
    assert versions == {"numpy": "2.0.2", "pandas": "2.2.3"}


def test_write_constraint_file_sorts_and_pins(tmp_path: Path) -> None:
    target = tmp_path / "constraints.txt"
    with _patched_get(_FAKE_LOCKFILE):
        ok = write_constraint_file(str(target))
    assert ok is True
    assert target.read_text() == "numpy==2.0.2\npandas==2.2.3\n"


def test_write_constraint_file_returns_false_on_fetch_failure(
    tmp_path: Path,
) -> None:
    target = tmp_path / "constraints.txt"
    with patch(
        "marimo._pyodide.pyodide_constraints.requests.get",
        side_effect=OSError("offline"),
    ):
        ok = write_constraint_file(str(target))
    assert ok is False
    # We didn't write anything.
    assert not target.exists()


def test_normalize_package_name_pep503() -> None:
    assert normalize_package_name("My_Pkg.Name") == "my-pkg-name"
    assert normalize_package_name("Pkg__Name") == "pkg-name"
    assert normalize_package_name("simple") == "simple"


def test_lockfile_env_override_reads_local_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MARIMO_PYODIDE_LOCK_FILE skips the network and reads from disk."""
    lockfile = tmp_path / "pyodide-lock.json"
    lockfile.write_text(json.dumps(_FAKE_LOCKFILE))
    monkeypatch.setenv("MARIMO_PYODIDE_LOCK_FILE", str(lockfile))

    # requests.get would raise loudly if hit; assert we never call it.
    with patch(
        "marimo._pyodide.pyodide_constraints.requests.get",
        side_effect=AssertionError("requests.get should not be called"),
    ):
        versions = fetch_pyodide_package_versions()
    assert versions == {"numpy": "2.0.2", "pandas": "2.2.3"}


def test_lockfile_env_override_missing_file_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bad path bubbles the OSError so write_constraint_file degrades."""
    monkeypatch.setenv("MARIMO_PYODIDE_LOCK_FILE", "/no/such/file")
    with pytest.raises(OSError):
        fetch_pyodide_package_versions()
