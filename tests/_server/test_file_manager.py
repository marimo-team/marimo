from __future__ import annotations

import os
import sys
import tempfile
from typing import Generator

import pytest

from marimo import __version__
from marimo._ast.cell import CellConfig
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_manager import AppFileManager
from marimo._server.models.models import SaveNotebookRequest

save_request = SaveNotebookRequest(
    cell_ids=["1"],
    filename="save_existing.py",
    codes=["import marimo as mo"],
    names=["my_cell"],
    configs=[CellConfig(hide_code=True)],
)


@pytest.fixture
def app_file_manager() -> Generator[AppFileManager, None, None]:
    """
    Creates an AppFileManager instance with a temporary file.
    """
    # Create a temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)

    temp_file.write(
        """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def __():
    import marimo as mo
    return mo,
if __name__ == "__main__":
    app.run()
""".encode()
    )

    temp_file.close()

    # Instantiate AppFileManager with the temporary file and a mock app
    manager = AppFileManager(filename=temp_file.name)
    yield manager

    # Clean up the temporary file
    if os.path.exists(temp_file.name):
        os.remove(temp_file.name)


def test_rename_same_filename(app_file_manager: AppFileManager) -> None:
    initial_filename = app_file_manager.filename or ""
    app_file_manager.rename(initial_filename)
    assert app_file_manager.filename == initial_filename


def test_rename_to_existing_filename(app_file_manager: AppFileManager) -> None:
    existing_filename = "existing_file.py"
    with open(existing_filename, "w") as f:
        f.write("This is a test file.")
    try:
        with pytest.raises(HTTPException) as e:  # noqa: PT012
            app_file_manager.rename(existing_filename)
        assert e.value.status_code == HTTPStatus.BAD_REQUEST
    finally:
        os.remove(existing_filename)


def test_successful_rename(app_file_manager: AppFileManager) -> None:
    existing_filename = os.path.abspath(app_file_manager.filename or "")
    new_filename = os.path.join(
        os.path.dirname(existing_filename), "new_file.py"
    )
    if os.path.exists(new_filename):
        os.remove(new_filename)
    try:
        app_file_manager.rename(new_filename)
        assert app_file_manager.filename == new_filename
    finally:
        os.remove(new_filename)


def test_rename_exception(app_file_manager: AppFileManager) -> None:
    new_filename = "/invalid/path/new_filename.py"
    with pytest.raises(HTTPException) as e:  # noqa: PT012
        app_file_manager.rename(new_filename)
    assert e.value.status_code == HTTPStatus.SERVER_ERROR


def test_rename_create_new_file(app_file_manager: AppFileManager) -> None:
    app_file_manager.filename = None
    new_filename = "new_file.py"
    if os.path.exists(new_filename):
        os.remove(new_filename)
    try:
        app_file_manager.rename(new_filename)
        assert os.path.exists(new_filename)
    finally:
        os.remove(new_filename)


def test_rename_create_new_directory_file(
    app_file_manager: AppFileManager,
) -> None:
    app_file_manager.filename = None
    new_directory = "new_directory"
    new_filename = os.path.join(new_directory, "new_file.py")
    if os.path.exists(new_filename):
        os.remove(new_filename)
    if os.path.exists(new_directory):
        os.rmdir(new_directory)
    try:
        app_file_manager.rename(new_filename)
        assert os.path.exists(new_filename)
    finally:
        os.remove(new_filename)
        os.rmdir(new_directory)


def test_rename_different_filetype(app_file_manager: AppFileManager) -> None:
    initial_filename = app_file_manager.filename
    assert initial_filename
    assert initial_filename.endswith(".py")
    with open(initial_filename, "r") as f:
        contents = f.read()
        assert "app = marimo.App()" in contents
        assert "marimo-version" not in contents
    app_file_manager.rename(initial_filename[:-3] + ".md")
    next_filename = app_file_manager.filename
    assert next_filename
    assert next_filename.endswith(".md")
    with open(next_filename, "r") as f:
        contents = f.read()
        assert "marimo-version" in contents
        assert "app = marimo.App()" not in contents


def test_save_app_config_valid(app_file_manager: AppFileManager) -> None:
    app_file_manager.filename = "app_config.py"
    try:
        app_file_manager.save_app_config({})
        with open(app_file_manager.filename, "r", encoding="utf-8") as f:
            contents = f.read()
        assert "app = marimo.App" in contents
    finally:
        os.remove(app_file_manager.filename)


@pytest.mark.skipif(
    condition=sys.platform == "win32",
    reason="filename is not invalid on Windows",
)
def test_save_app_config_exception(app_file_manager: AppFileManager) -> None:
    app_file_manager.filename = "/invalid/path/app_config.py"
    with pytest.raises(HTTPException) as e:  # noqa: PT012
        app_file_manager.save_app_config({})
    assert e.value.status_code == HTTPStatus.SERVER_ERROR


def test_save_filename_change_not_allowed(
    app_file_manager: AppFileManager,
) -> None:
    app_file_manager.filename = "original.py"
    save_request.filename = "new.py"
    with pytest.raises(HTTPException) as e:  # noqa: PT012
        app_file_manager.save(save_request)
    assert e.value.status_code == HTTPStatus.BAD_REQUEST


def test_save_existing_filename(app_file_manager: AppFileManager) -> None:
    existing_filename = "existing_file.py"
    with open(existing_filename, "w") as f:
        f.write("This is a test file.")
    save_request.filename = existing_filename
    try:
        with pytest.raises(HTTPException) as e:  # noqa: PT012
            app_file_manager.save(save_request)
        assert e.value.status_code == HTTPStatus.BAD_REQUEST
    finally:
        os.remove(existing_filename)


def test_save_successful(app_file_manager: AppFileManager) -> None:
    save_request.filename = app_file_manager.filename or ""
    try:
        app_file_manager.save(save_request)
        assert os.path.exists(save_request.filename)
    finally:
        os.remove(save_request.filename)


def test_save_cannot_rename(app_file_manager: AppFileManager) -> None:
    save_request.filename = "/invalid/path/save_exception.py"
    with pytest.raises(HTTPException) as e:
        app_file_manager.save(save_request)
    assert e.value.status_code == HTTPStatus.BAD_REQUEST


def test_read_valid_filename(app_file_manager: AppFileManager) -> None:
    expected_content = "This is a test read."
    app_file_manager.filename = "test_read.py"
    try:
        with open(app_file_manager.filename, "w", encoding="utf-8") as f:
            f.write(expected_content)
        content = app_file_manager.read_file()
        assert content == expected_content
    finally:
        os.remove(app_file_manager.filename)


def test_read_unnamed_notebook(app_file_manager: AppFileManager) -> None:
    app_file_manager.filename = None
    with pytest.raises(HTTPException) as e:
        app_file_manager.read_file()
    assert e.value.status_code == HTTPStatus.BAD_REQUEST


def test_read_layout(app_file_manager: AppFileManager) -> None:
    layout = app_file_manager.read_layout_config()
    assert layout is None


def test_to_code(app_file_manager: AppFileManager) -> None:
    code = app_file_manager.to_code()
    assert code == "\n".join(
        [
            "import marimo",
            "",
            f'__generated_with = "{__version__}"',
            "app = marimo.App()",
            "",
            "",
            "@app.cell",
            "def _():",
            "    import marimo as mo",
            "    return (mo,)",
            "",
            "",
            'if __name__ == "__main__":',
            "    app.run()",
            "",
        ]
    )


def test_reload_reorders_cells() -> None:
    """Test that reload() reorders cell IDs based on similarity to previous cells."""
    # Create a temporary file with initial content
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    initial_content = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def cell1():
    x = 1
    return x

@app.cell
def cell2():
    y = 2
    return y

if __name__ == "__main__":
    app.run()
"""
    temp_file.write(initial_content.encode())
    temp_file.close()

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=temp_file.name)
    original_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert original_cell_ids == ["Hbol", "MJUe"]

    # Modify the file content - swap the cells but keep similar content
    modified_content = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def cell2():
    y = 2
    return y

@app.cell
def cell1():
    x = 1
    return x

if __name__ == "__main__":
    app.run()
"""
    with open(temp_file.name, "w") as f:
        f.write(modified_content)

    # Reload the file
    manager.reload()

    # The cell IDs should be reordered to match the original code
    reloaded_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert len(reloaded_cell_ids) == len(original_cell_ids)
    assert reloaded_cell_ids == ["MJUe", "Hbol"]

    # Clean up
    os.remove(temp_file.name)


def test_reload_updates_content() -> None:
    """Test that reload() updates the file contents correctly."""
    # Create a temporary file with initial content
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    initial_content = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def cell1():
    x = 1
    return x

if __name__ == "__main__":
    app.run()
"""
    temp_file.write(initial_content.encode())
    temp_file.close()

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=temp_file.name)
    original_code = list(manager.app.cell_manager.codes())[0]
    assert "x = 1" in original_code

    # Modify the file content
    modified_content = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def cell1():
    x = 42  # Changed value
    return x

if __name__ == "__main__":
    app.run()
"""
    with open(temp_file.name, "w") as f:
        f.write(modified_content)

    # Reload the file
    manager.reload()

    # Check that the code was updated
    reloaded_code = list(manager.app.cell_manager.codes())[0]
    assert "x = 42" in reloaded_code
    assert "x = 1" not in reloaded_code

    # Clean up
    os.remove(temp_file.name)


def test_reload_updates_new_cell() -> None:
    """Test that reload() updates the file contents correctly."""

    # Create a temp file with initial content
    temp_file = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    initial_content = """
import marimo
app = marimo.App()

@app.cell
def cell1():
    x = 1
    return x

if __name__ == "__main__":
    app.run()
"""
    temp_file.write(initial_content.encode())
    temp_file.close()

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=temp_file.name)
    assert len(list(manager.app.cell_manager.codes())) == 1
    original_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert original_cell_ids == ["Hbol"]

    # Modify the file content to add a new cell
    modified_content = """
import marimo
app = marimo.App()

@app.cell
def cell2():
    y = 2
    return y

@app.cell
def cell1():
    x = 1
    return x

if __name__ == "__main__":
    app.run()
"""
    with open(temp_file.name, "w") as f:
        f.write(modified_content)

    # Reload the file
    manager.reload()

    # Check that the new cell was added
    codes = list(manager.app.cell_manager.codes())
    assert len(codes) == 2
    assert "y = 2" in codes[0]
    assert "x = 1" in codes[1]
    next_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert next_cell_ids == ["MJUe", "Hbol"]

    # Clean up
    os.remove(temp_file.name)
