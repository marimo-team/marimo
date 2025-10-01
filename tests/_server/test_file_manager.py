from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from marimo import __version__
from marimo._ast.cell import CellConfig
from marimo._server.api.status import HTTPException, HTTPStatus
from marimo._server.file_manager import AppFileManager
from marimo._server.models.models import SaveNotebookRequest
from marimo._types.ids import CellId_t
from marimo._utils.cell_matching import similarity_score

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

save_request = SaveNotebookRequest(
    cell_ids=["1"],
    filename="save_existing.py",
    codes=["import marimo as mo"],
    names=["my_cell"],
    configs=[CellConfig(hide_code=True)],
)


@pytest.fixture
def app_file_manager(tmp_path: Path) -> Generator[AppFileManager, None, None]:
    """
    Creates an AppFileManager instance with a temporary file.
    """
    # Create a temporary file
    temp_file = tmp_path / "test_app.py"

    temp_file.write_text(
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
"""
    )

    # Instantiate AppFileManager with the temporary file and a mock app
    manager = AppFileManager(filename=str(temp_file))
    return manager

    # No manual cleanup needed - pytest handles it automatically


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
    with open(initial_filename) as f:
        contents = f.read()
        assert "app = marimo.App()" in contents
        assert "marimo-version" not in contents
    app_file_manager.rename(initial_filename[:-3] + ".md")
    next_filename = app_file_manager.filename
    assert next_filename
    assert next_filename.endswith(".md")
    with open(next_filename) as f:
        contents = f.read()
        assert "marimo-version" in contents
        assert "app = marimo.App()" not in contents


def test_rename_to_qmd(app_file_manager: AppFileManager) -> None:
    initial_filename = app_file_manager.filename
    assert initial_filename
    assert initial_filename.endswith(".py")
    with open(initial_filename) as f:
        contents = f.read()
        assert "app = marimo.App()" in contents
        assert "marimo-team/marimo" not in contents
        assert "marimo-version" not in contents
    app_file_manager.rename(initial_filename[:-3] + ".qmd")
    next_filename = app_file_manager.filename
    assert next_filename
    assert next_filename.endswith(".qmd")
    with open(next_filename) as f:
        contents = f.read()
        assert "marimo-version" in contents
        assert "filters:" in contents
        assert "marimo-team/marimo" in contents
        assert "app = marimo.App()" not in contents


def test_save_app_config_valid(app_file_manager: AppFileManager) -> None:
    app_file_manager.filename = "app_config.py"
    try:
        app_file_manager.save_app_config({})
        with open(app_file_manager.filename, encoding="utf-8") as f:
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


def test_save_with_header(
    app_file_manager: AppFileManager, tmp_path: Path
) -> None:
    file = tmp_path / "test_save_with_header.py"
    file.write_text("""
# This is a header

import marimo
app = marimo.App()

@app.cell
def _():
    print(1)
    return
""")
    app_file_manager.filename = str(file)
    assert app_file_manager.path is not None
    app_file_manager.save(
        SaveNotebookRequest(
            cell_ids=[CellId_t("1")],
            filename=str(file),
            codes=["print(2)"],
            names=["_"],
            configs=[CellConfig(hide_code=True)],
        )
    )
    new_contents = file.read_text()
    assert "# This is a header" in new_contents
    assert "print(2)" in new_contents
    assert "print(1)" not in new_contents


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
            "    return",
            "",
            "",
            'if __name__ == "__main__":',
            "    app.run()",
            "",
        ]
    )


def test_reload_reorders_cells(tmp_path: Path) -> None:
    """Test that reload() reorders cell IDs based on similarity to previous cells."""
    # Create a temporary file with initial content
    temp_file = tmp_path / "test_reload.py"
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
    temp_file.write_text(initial_content)

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=str(temp_file))
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
    temp_file.write_text(modified_content)

    # Reload the file
    changed_cell_ids = manager.reload()

    # The cell IDs should be reordered to match the original code
    reloaded_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert len(reloaded_cell_ids) == len(original_cell_ids)
    assert reloaded_cell_ids == ["MJUe", "Hbol"]
    assert changed_cell_ids == set()


def test_reload_updates_content(tmp_path: Path) -> None:
    """Test that reload() updates the file contents correctly."""
    # Create a temporary file with initial content
    temp_file = tmp_path / "test_reload_content.py"
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
    temp_file.write_text(initial_content)

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=str(temp_file))
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
    temp_file.write_text(modified_content)

    # Reload the file
    changed_cell_ids = manager.reload()

    # Check that the code was updated
    reloaded_code = list(manager.app.cell_manager.codes())[0]
    assert "x = 42" in reloaded_code
    assert "x = 1" not in reloaded_code
    assert changed_cell_ids == {"Hbol"}


def test_reload_updates_new_cell(tmp_path: Path) -> None:
    """Test that reload() updates the file contents correctly."""

    # Create a temp file with initial content
    temp_file = tmp_path / "test_reload_new_cell.py"
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
    temp_file.write_text(initial_content)

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=str(temp_file))
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
    temp_file.write_text(modified_content)

    # Reload the file
    changed_cell_ids = manager.reload()

    # Check that the new cell was added
    codes = list(manager.app.cell_manager.codes())
    assert len(codes) == 2
    assert "y = 2" in codes[0]
    assert "x = 1" in codes[1]
    next_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert next_cell_ids == ["MJUe", "Hbol"]
    assert changed_cell_ids == {"MJUe"}


def test_rename_with_special_chars(
    app_file_manager: AppFileManager, tmp_path: Path
) -> None:
    """Test that renaming files with special characters works."""
    # Create a temporary file
    initial_path = tmp_path / "test.py"
    initial_path.write_text("import marimo")
    app_file_manager.filename = str(initial_path)

    # Try to rename to path with special characters
    new_path = tmp_path / "test & space.py"
    app_file_manager.rename(str(new_path))
    assert app_file_manager.filename == str(new_path)
    assert new_path.exists()


def test_reload_reinitializes_graph(tmp_path: Path) -> None:
    """Test that reload() properly reinitializes the graph with new cells."""
    # Create a temporary file
    tmp_file = tmp_path / "test.py"

    # Initial content with one cell
    tmp_file.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def cell1():
    x = 1
    return x

if __name__ == "__main__":
    app.run()
"""
    )

    cell_one = "Hbol"
    cell_two = "MJUe"

    # Create the file manager and load the app
    manager = AppFileManager(tmp_file)

    # Force initialization to create the graph
    assert manager.app._app._initialized is False
    assert manager.app.graph is not None
    assert manager.app._app._initialized is True

    # Check initial graph state
    cell_ids = set(manager.app.cell_manager.cell_ids())
    assert len(cell_ids) == 1
    assert cell_ids == {cell_one}

    # Check the graph has the correct cells
    assert manager.app.graph.cells.keys() == {cell_one}
    assert manager.app.graph.get_defining_cells("x") == {cell_one}

    # Modify file with an additional cell
    tmp_file.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def cell2():
    y = x + 1
    return y

@app.cell
def cell1():
    x = 1
    return x

if __name__ == "__main__":
    app.run()
"""
    )

    # Reload the app
    changed_cell_ids = manager.reload()
    assert changed_cell_ids == {cell_two}

    # Check that the graph was updated
    assert manager.app._app._initialized is False
    assert manager.app.graph is not None
    assert manager.app._app._initialized is True

    # Verify graph has both cells
    assert len(list(manager.app.graph.cells)) == 2

    # Verify edge exists between cell1 and cell2 (dependency)
    cell_ids = list(manager.app.cell_manager.cell_ids())
    assert cell_ids == [cell_two, cell_one]
    assert manager.app.cell_manager.get_cell_code(cell_one) == "x = 1"
    assert manager.app.cell_manager.get_cell_code(cell_two) == "y = x + 1"

    # Check that cell2 depends on cell1 in the graph
    assert manager.app.graph.get_defining_cells("x") == {cell_one}
    assert manager.app.graph.get_defining_cells("y") == {cell_two}

    # Modify the file to remove the dependency
    tmp_file.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def cell2():
    y = 2 + 1
    return y

if __name__ == "__main__":
    app.run()
"""
    )

    # The result is that cell1 is removed since similarity_score is closer to
    # cell2
    # NB. Lower is better for similarity_score
    new_code = "y = 2 + 1"
    assert similarity_score(
        manager.app.cell_manager.get_cell_code(cell_one), new_code
    ) > similarity_score(
        manager.app.cell_manager.get_cell_code(cell_two), new_code
    )

    # Reload the app
    changed_cell_ids = manager.reload()
    # Technically cell 1 did change since it was deleted.
    assert changed_cell_ids == {cell_one, cell_two}

    # Verify cell_manager has only one cell
    cell_ids = list(manager.app.cell_manager.cell_ids())
    assert cell_ids == [cell_two]

    # Verify graph has only one cell
    graph_ids = list(manager.app.graph.cells)
    assert graph_ids == [cell_two]

    # Check that the graph was updated
    assert manager.app.graph.get_defining_cells("y") == {cell_two}

    # Check the contents of the cell
    assert manager.app.cell_manager.get_cell_code(cell_two) == new_code


def test_default_app_settings(tmp_path: Path) -> None:
    """Test that default_sql_output and default_width are properly applied."""
    # Test with custom defaults
    manager = AppFileManager(
        filename=None,
        default_width="full",
        default_sql_output="polars",
    )
    assert manager.app.config.width == "full"
    assert manager.app.config.sql_output == "polars"

    # Test with None defaults (should use system defaults)
    manager = AppFileManager(filename=None)

    assert manager.app.config.width == "compact"
    assert manager.app.config.sql_output == "auto"

    # Existing file does not get overwritten
    tmp_file = tmp_path / "test.py"
    tmp_file.write_text(
        """
import marimo
app = marimo.App(sql_output="lazy-polars", width="columns")
"""
    )
    manager = AppFileManager(
        filename=tmp_file,
        default_width="full",
        default_sql_output="polars",
    )
    assert manager.app.config.width == "columns"
    assert manager.app.config.sql_output == "lazy-polars"


def test_overload_app_settings() -> None:
    """Test that private env can overload app settings."""
    # Test with defaults
    manager = AppFileManager(
        filename=None,
    )
    assert manager.app.config.auto_download == []
    assert manager.app.config.sql_output == "auto"

    # Test with env set
    try:
        os.environ["_MARIMO_APP_OVERLOAD_SQL_OUTPUT"] = "polars"
        os.environ["_MARIMO_APP_OVERLOAD_AUTO_DOWNLOAD"] = "[html,ipynb]"
        manager = AppFileManager(filename=None)

        assert manager.app.config.auto_download == ["html", "ipynb"]
        assert manager.app.config.sql_output == "polars"
    finally:
        os.environ.pop("_MARIMO_APP_OVERLOAD_SQL_OUTPUT", None)
        os.environ.pop("_MARIMO_APP_OVERLOAD_AUTO_DOWNLOAD", None)


def test_reload_detects_deleted_cells(tmp_path: Path) -> None:
    """Test that reload() correctly detects deleted cells."""
    # Create a temporary file with two cells
    temp_file = tmp_path / "test_reload_deleted.py"
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
    temp_file.write_text(initial_content)

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=str(temp_file))
    original_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert len(original_cell_ids) == 2

    # Modify the file content - remove one cell
    modified_content = """
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
    temp_file.write_text(modified_content)

    # Reload the file
    changed_cell_ids = manager.reload()

    # The deleted cell should be included in changed_cell_ids
    reloaded_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert len(reloaded_cell_ids) == 1
    deleted_cell_ids = set(original_cell_ids) - set(reloaded_cell_ids)
    assert len(deleted_cell_ids) == 1
    assert deleted_cell_ids.issubset(changed_cell_ids)


def test_reload_detects_multiple_deleted_cells(tmp_path: Path) -> None:
    """Test that reload() correctly detects multiple deleted cells."""
    # Create a temporary file with three cells
    temp_file = tmp_path / "test_reload_multiple_deleted.py"
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

@app.cell
def cell3():
    z = 3
    return z

if __name__ == "__main__":
    app.run()
"""
    temp_file.write_text(initial_content)

    # Initialize AppFileManager with the temp file
    manager = AppFileManager(filename=str(temp_file))
    original_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert len(original_cell_ids) == 3

    # Modify the file content - keep only one cell
    modified_content = """
import marimo
__generated_with = "0.0.1"
app = marimo.App()

@app.cell
def cell2():
    y = 2
    return y

if __name__ == "__main__":
    app.run()
"""
    temp_file.write_text(modified_content)

    # Reload the file
    changed_cell_ids = manager.reload()

    # Two cells should be deleted and included in changed_cell_ids
    reloaded_cell_ids = list(manager.app.cell_manager.cell_ids())
    assert len(reloaded_cell_ids) == 1
    deleted_cell_ids = set(original_cell_ids) - set(reloaded_cell_ids)
    assert len(deleted_cell_ids) == 2
    assert deleted_cell_ids.issubset(changed_cell_ids)
