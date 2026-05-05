# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path

import pytest

from marimo._session.notebook import AppFileManager
from marimo._utils.http import HTTPException
from tests.mocks import EDGE_CASE_FILENAMES


class TestAppFileManagerFilenames:
    """Test AppFileManager filename handling with unicode, spaces, and special characters."""

    @pytest.mark.parametrize("filename", EDGE_CASE_FILENAMES)
    def test_app_file_manager_operations_with_edge_case_filenames(
        self, filename: str, tmp_path: Path
    ) -> None:
        """Test AppFileManager core operations with problematic filenames."""
        file_path = tmp_path / filename
        content = "import marimo as mo\n\napp = mo.App()\n\n@app.cell\ndef __():\n    return\n"

        # Create and test initialization
        Path(file_path).write_text(content, encoding="utf-8")
        file_manager = AppFileManager(file_path)

        assert file_manager.filename == str(file_path)
        assert file_manager.path == str(file_path)
        assert file_manager.is_notebook_named

        # Test reading
        read_content = file_manager.read_file()
        assert read_content == content

        # Test rename to new problematic filename
        new_filename = f"new_{filename}"
        new_path = tmp_path / new_filename

        file_manager.rename(str(new_path))
        assert file_manager.filename == str(new_path)
        assert Path(new_path).exists()
        assert not Path(file_path).exists()

    def test_app_file_manager_rename_collision_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Test that renaming to existing filename raises HTTPException."""
        original_path = tmp_path / "original.py"
        target_path = tmp_path / "café notebook.py"

        # Create both files
        Path(original_path).write_text("# Original", encoding="utf-8")
        Path(target_path).write_text("# Target", encoding="utf-8")

        file_manager = AppFileManager(original_path)

        with pytest.raises(HTTPException) as exc_info:
            file_manager.rename(str(target_path))

        assert "already exists" in str(exc_info.value.detail)

    def test_from_app_snapshots_relative_filename_to_absolute(
        self, tmp_path: Path
    ) -> None:
        # ``AppFileManager.from_app(..., filename=...)`` must snapshot a
        # relative ``filename`` to an absolute path at call time so a
        # later ``chdir`` cannot shift which file ``self.path`` resolves
        # to (which is what ``AppMetadata.filename`` / ``__file__`` are
        # built from).
        import os

        from marimo._ast.app import App, InternalApp

        nb_dir = tmp_path / "notebooks"
        nb_dir.mkdir()
        original_cwd = os.getcwd()
        try:
            os.chdir(nb_dir)
            manager = AppFileManager.from_app(
                InternalApp(App()), filename="nb.py"
            )
            expected = str(nb_dir / "nb.py")
            os.chdir(tmp_path)
            assert manager.path == expected
        finally:
            os.chdir(original_cwd)
