# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from marimo._server.files.roots import resolve_file_roots

if TYPE_CHECKING:
    from pathlib import Path


def test_resolve_file_roots_orders_and_names_roots(tmp_path: Path) -> None:
    primary = tmp_path / "project"
    shared = tmp_path / "shared"
    unnamed = tmp_path / "unnamed"
    primary.mkdir()
    shared.mkdir()
    unnamed.mkdir()

    roots = resolve_file_roots(
        str(primary),
        {
            "folders": [
                {"path": str(shared), "name": "Shared data"},
                {"path": str(unnamed)},
            ]
        },
    )

    assert [(root.path, root.name, root.is_primary) for root in roots] == [
        (str(primary.resolve()), "project", True),
        (str(shared.resolve()), "Shared data", False),
        (str(unnamed.resolve()), "unnamed", False),
    ]


def test_resolve_file_roots_skips_invalid_and_duplicate_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = tmp_path / "project"
    valid = tmp_path / "valid"
    inaccessible = tmp_path / "inaccessible"
    file_path = tmp_path / "file.txt"
    primary.mkdir()
    valid.mkdir()
    inaccessible.mkdir()
    file_path.write_text("not a directory")

    real_access = __import__("os").access
    monkeypatch.setattr(
        "marimo._server.files.roots.os.access",
        lambda path, mode: (
            False
            if path == str(inaccessible.resolve())
            else real_access(path, mode)
        ),
    )
    warning = Mock()
    monkeypatch.setattr("marimo._server.files.roots.LOGGER.warning", warning)

    roots = resolve_file_roots(
        str(primary),
        {
            "folders": [
                {"path": "relative"},
                {"path": str(tmp_path / "missing")},
                {"path": str(file_path)},
                {"path": str(inaccessible)},
                {"path": str(primary)},
                {"path": str(valid)},
                {"path": str(valid / ".." / "valid")},
            ]
        },
    )

    assert [root.path for root in roots] == [
        str(primary.resolve()),
        str(valid.resolve()),
    ]
    assert warning.call_count == 6


def test_resolve_file_roots_uses_basename_for_blank_name(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "project"
    shared = tmp_path / "shared"
    primary.mkdir()
    shared.mkdir()

    roots = resolve_file_roots(
        str(primary),
        {"folders": [{"path": str(shared), "name": "  "}]},
    )

    assert roots[1].name == "shared"


def test_resolve_file_roots_warns_when_folder_does_not_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    primary = tmp_path / "project"
    missing = tmp_path / "missing"
    primary.mkdir()
    warning = Mock()
    monkeypatch.setattr("marimo._server.files.roots.LOGGER.warning", warning)

    roots = resolve_file_roots(
        str(primary),
        {"folders": [{"path": str(missing)}]},
    )

    assert len(roots) == 1
    warning.assert_called_once_with(
        "Ignoring file browser root %r: %s",
        str(missing),
        "path does not exist",
    )


@pytest.mark.parametrize(
    "config",
    [
        {"folders": "not-a-list"},
        {"folders": ["not-a-table"]},
    ],
)
def test_resolve_file_roots_ignores_malformed_config(
    tmp_path: Path,
    config: object,
) -> None:
    primary = tmp_path / "project"
    primary.mkdir()

    roots = resolve_file_roots(str(primary), config)  # type: ignore[arg-type]

    assert len(roots) == 1
    assert roots[0].is_primary is True
