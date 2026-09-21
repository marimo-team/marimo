from __future__ import annotations

from pathlib import Path

import pytest

import marimo as mo
from marimo._runtime.context import get_context
from marimo._runtime.context.filename import notebook_filename


@pytest.mark.parametrize("filename", [None, ""])
def test_unknown_filename_uses_cwd(filename: str | None) -> None:
    with notebook_filename(filename):
        assert (mo.notebook_dir(), mo.notebook_location()) == (
            Path.cwd(),
            Path.cwd(),
        )


def test_filename_preserves_symlinks(tmp_path: Path) -> None:
    directory = tmp_path / "original"
    directory.mkdir()
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(directory, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Creating symlinks is not supported")

    with notebook_filename(str(alias / "notebook.py")):
        assert (mo.notebook_dir(), mo.notebook_location()) == (alias, alias)


def test_filename_does_not_override_kernel_context(
    execution_kernel, tmp_path: Path
) -> None:
    del execution_kernel
    context = get_context()
    expected = (mo.notebook_dir(), mo.notebook_location(), mo.app_meta().mode)
    with notebook_filename(str(tmp_path / "other.py")):
        assert get_context() is context
        assert (
            mo.notebook_dir(),
            mo.notebook_location(),
            mo.app_meta().mode,
        ) == expected
    assert get_context() is context
