from __future__ import annotations

from typing import TYPE_CHECKING, get_type_hints

import pytest

from marimo import __version__
from marimo._ast.app_config import _AppConfig
from marimo._islands._island_generator import (
    MarimoIslandGenerator,
)
from marimo._schemas.serialization import (
    AppInstantiation,
    CellDef,
    NotebookSerialization,
)
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from pathlib import Path

snapshot = snapshotter(__file__)


def _notebook(
    cells: list[CellDef],
    *,
    options: dict[str, object] | None = None,
    filename: str | None = None,
) -> NotebookSerialization:
    return NotebookSerialization(
        app=AppInstantiation(options=options or {}),
        cells=cells,
        filename=filename,
    )


def test_add_code():
    generator = MarimoIslandGenerator()
    generator.add_code("print('Hello, World!')")

    # Check if the cell was added
    assert len(list(generator._app.cell_manager.cells())) == 1


async def test_build():
    generator = MarimoIslandGenerator()
    generator.add_code("print('Hello, World!')")

    # Check if the app is built successfully
    app = await generator.build()
    assert app is not None
    assert generator.has_run is True

    # Check if build() raises an error when called more than once
    with pytest.raises(ValueError):
        await generator.build()


async def test_render():
    generator = MarimoIslandGenerator()
    block1 = generator.add_code("import marimo as mo")
    block2 = generator.add_code("mo.md('Hello, islands!')")
    imageBlock = generator.add_code(
        "mo.image('https://example.com/image.png')"
    )
    jsonBlock = generator.add_code("{'key': 'value'}")
    arrayBlock = generator.add_code("[1, mo.md('Hello')]")

    await generator.build()

    with pytest.raises(ValueError) as e:
        block1.render(
            display_code=False, display_output=False, is_reactive=False
        )
    assert str(e.value) == "You must include either code or output"

    # Check if render works after build() is called
    snapshot("island.txt", block2.render())

    snapshot("island-no-code.txt", block2.render(display_code=False))

    snapshot("island-no-output.txt", block2.render(display_output=False))

    snapshot(
        "island-mimetypes.txt",
        "\n".join(
            [
                block2.render(display_code=False),
                imageBlock.render(display_code=False),
                jsonBlock.render(display_code=False),
                arrayBlock.render(display_code=False),
            ]
        ),
    )


async def test_render_multiline_markdown():
    generator = MarimoIslandGenerator()
    stub = generator.add_code(
        """
        import marimo as mo
        mo.md(
            \"\"\"
            # Hello, Markdown!

            This is a paragsraph.

            ```python3
            mo.md(
                '''
                # Hello, Markdown!

                This is a paragraph.
                '''
            )
            ```
            \"\"\"
        )
        """
    )
    await generator.build()
    snapshot("markdown.txt", stub.render())


async def test_from_file(tmp_path: Path):
    # Create a temporary marimo file
    marimo_file = tmp_path / "temp_marimo_file.py"
    marimo_file.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def __():
    import marimo as mo
    mo.md("# Hello, Marimo!")
    return (mo,)

@app.cell
def __(mo):
    x = 42
    mo.md(f"The answer is {x}")
    return (x,)
        """
    )

    generator = MarimoIslandGenerator.from_file(str(marimo_file))

    # Check if stubs were created correctly
    assert len(generator._stubs) == 2
    assert (
        generator._stubs[0].code.strip()
        == 'import marimo as mo\nmo.md("# Hello, Marimo!")'
    )
    assert (
        generator._stubs[1].code.strip()
        == 'x = 42\nmo.md(f"The answer is {x}")'
    )

    # Build and check outputs
    await generator.build()
    stub1 = generator._stubs[0]
    stub2 = generator._stubs[1]
    assert stub1.output is not None
    assert stub2.output is not None
    assert "Hello, Marimo!" in stub1.output.data
    assert "The answer is 42" in stub2.output.data


async def test_from_file_propagates_filename_to_cells(tmp_path: Path):
    # Regression test for #9391: cells rendered through
    # ``MarimoIslandGenerator.from_file()`` must see ``__file__`` and
    # ``mo.notebook_dir()`` resolve to the notebook source, not to the
    # host process's ``__main__`` (which under installed CLIs is a
    # launcher shim).
    marimo_file = tmp_path / "nb.py"
    marimo_file.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def __():
    import marimo as mo
    return (mo,)

@app.cell
def __(mo):
    mo.md(f"FILE={__file__} | DIR={mo.notebook_dir()}")
    return ()
        """
    )

    generator = MarimoIslandGenerator.from_file(str(marimo_file))
    await generator.build()

    captured = generator._stubs[1].output
    assert captured is not None
    data = captured.data
    assert str(marimo_file) in data, (
        f"expected __file__ to resolve to {marimo_file}, got: {data}"
    )
    assert str(marimo_file.parent) in data, (
        f"expected notebook_dir() to resolve to {marimo_file.parent}, got: {data}"
    )


async def test_from_file_resolves_relative_path_at_capture_time(
    tmp_path: Path,
) -> None:
    # Companion to ``test_from_file_propagates_filename_to_cells``:
    # passing a relative path to ``from_file`` should snapshot the
    # absolute path immediately, so a ``chdir`` between ``from_file``
    # and ``build`` cannot change which file cells see.
    import os

    nb_dir = tmp_path / "notebooks"
    nb_dir.mkdir()
    marimo_file = nb_dir / "nb.py"
    marimo_file.write_text(
        """
import marimo

app = marimo.App()

@app.cell
def __():
    import marimo as mo
    return (mo,)

@app.cell
def __(mo):
    mo.md(f"FILE={__file__}")
    return ()
        """
    )

    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()

    original_cwd = os.getcwd()
    try:
        os.chdir(nb_dir)
        generator = MarimoIslandGenerator.from_file("nb.py")
        # Move to an unrelated directory before ``build`` runs.
        os.chdir(other_dir)
        await generator.build()
    finally:
        os.chdir(original_cwd)

    captured = generator._stubs[1].output
    assert captured is not None
    data = captured.data
    assert str(marimo_file) in data, (
        f"expected __file__ to resolve to {marimo_file}, got: {data}"
    )
    # And the path shouldn't accidentally resolve under ``other_dir``.
    assert str(other_dir / "nb.py") not in data


async def test_from_ir_builds_notebook_serialization() -> None:
    notebook = _notebook(
        [
            CellDef(code="import marimo as mo"),
            CellDef(code='mo.md("# Hello, IR!")'),
        ],
    )

    generator = MarimoIslandGenerator._from_ir(notebook, app_id="page-a")
    stubs = generator.stubs

    assert len(stubs) == 2
    assert stubs[0].code == "import marimo as mo"
    assert stubs[1].code == 'mo.md("# Hello, IR!")'
    body_html = generator.render_body(include_init_island=False)
    assert 'data-app-id="page-a"' in body_html
    for cell_id in generator._app.cell_manager.cell_ids():
        assert f'data-cell-id="{cell_id}"' in body_html

    await generator.build()

    stub = generator.stubs[1]
    assert stub.output is not None
    assert "Hello, IR!" in stub.output.data


def test_stubs_returns_read_only_snapshot() -> None:
    generator = MarimoIslandGenerator()
    generator.add_code("x = 1")

    stubs = generator.stubs
    assert len(stubs) == 1
    assert stubs[0].code == "x = 1"

    generator.add_code("y = 2")
    assert len(stubs) == 1
    assert len(generator.stubs) == 2


def test_from_ir_type_hints_resolve() -> None:
    hints = get_type_hints(MarimoIslandGenerator._from_ir)

    assert hints["notebook"] is NotebookSerialization
    assert hints["return"] is MarimoIslandGenerator


def test_from_ir_applies_display_code_to_stubs() -> None:
    notebook = _notebook([CellDef(code="x = 1")])

    generator = MarimoIslandGenerator._from_ir(
        notebook,
        display_code=True,
    )

    html = generator.stubs[0].render()
    assert "<marimo-cell-code hidden>" not in html
    assert "x = 1" in html


def test_from_ir_preserves_app_config() -> None:
    notebook = _notebook(
        [],
        options={"width": "medium", "app_title": "IR App"},
    )

    generator = MarimoIslandGenerator._from_ir(notebook)

    body_html = generator.render_body()
    assert 'style="margin: auto; max-width: 1110px;"' in body_html

    html = generator.render_html()
    assert "<title> IR App </title>" in html


def test_from_ir_sanitizes_markdown_app_config() -> None:
    notebook = _notebook(
        [],
        options={"width": "medium", "author": "Marimo"},
        filename="notebook.md",
    )

    generator = MarimoIslandGenerator._from_ir(notebook)

    body_html = generator.render_body()
    assert 'style="margin: auto; max-width: 1110px;"' in body_html


async def test_from_ir_propagates_ir_filename_to_cells(tmp_path: Path) -> None:
    notebook_file = tmp_path / "nb.py"
    notebook_file.write_text("")
    notebook = _notebook(
        [
            CellDef(code="import marimo as mo"),
            CellDef(
                code=('mo.md(f"FILE={__file__} | DIR={mo.notebook_dir()}")')
            ),
        ],
        filename=str(notebook_file),
    )

    generator = MarimoIslandGenerator._from_ir(notebook)
    await generator.build()

    captured = generator.stubs[1].output
    assert captured is not None
    data = captured.data
    assert str(notebook_file) in data, (
        f"expected __file__ to resolve to {notebook_file}, got: {data}"
    )
    assert str(notebook_file.parent) in data, (
        f"expected notebook_dir() to resolve to {notebook_file.parent}, "
        f"got: {data}"
    )


async def test_from_ir_resolves_relative_path_at_capture_time(
    tmp_path: Path,
) -> None:
    import os

    notebook_dir = tmp_path / "notebooks"
    notebook_dir.mkdir()
    notebook_file = notebook_dir / "nb.py"
    notebook_file.write_text("")
    notebook = _notebook(
        [
            CellDef(code="import marimo as mo"),
            CellDef(code='mo.md(f"FILE={__file__}")'),
        ],
    )
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()

    original_cwd = os.getcwd()
    try:
        os.chdir(notebook_dir)
        generator = MarimoIslandGenerator._from_ir(notebook, filepath="nb.py")
        os.chdir(other_dir)
        await generator.build()
    finally:
        os.chdir(original_cwd)

    captured = generator.stubs[1].output
    assert captured is not None
    data = captured.data
    assert str(notebook_file) in data, (
        f"expected __file__ to resolve to {notebook_file}, got: {data}"
    )
    assert str(other_dir / "nb.py") not in data


async def test_from_ir_filepath_overrides_ir_filename(
    tmp_path: Path,
) -> None:
    ir_file = tmp_path / "ir.py"
    source_file = tmp_path / "source.ipynb"
    ir_file.write_text("")
    source_file.write_text("")
    notebook = _notebook(
        [
            CellDef(code="import marimo as mo"),
            CellDef(
                code=('mo.md(f"FILE={__file__} | DIR={mo.notebook_dir()}")')
            ),
        ],
        filename=str(ir_file),
    )

    generator = MarimoIslandGenerator._from_ir(
        notebook, filepath=str(source_file)
    )
    await generator.build()

    captured = generator.stubs[1].output
    assert captured is not None
    data = captured.data
    assert str(source_file) in data, (
        f"expected __file__ to resolve to {source_file}, got: {data}"
    )
    assert str(source_file.parent) in data, (
        f"expected notebook_dir() to resolve to {source_file.parent}, "
        f"got: {data}"
    )
    assert str(ir_file) not in data


async def test_from_ir_preserves_disabled_cell_config() -> None:
    notebook = _notebook(
        [
            CellDef(code="'disabled output'", options={"disabled": True}),
            CellDef(code="'active output'"),
        ],
    )

    generator = MarimoIslandGenerator._from_ir(notebook)

    body_html = generator.render_body(include_init_island=False)
    assert 'data-reactive="false"' in body_html
    assert 'data-reactive="true"' in body_html

    await generator.build()

    disabled_stub = generator.stubs[0]
    active_stub = generator.stubs[1]
    assert disabled_stub.output is None
    assert active_stub.output is not None
    assert "active output" in active_stub.output.data


async def test_from_ir_marks_transitively_disabled_cells_static() -> None:
    notebook = _notebook(
        [
            CellDef(code="x = 1", options={"disabled": True}),
            CellDef(code="x + 1"),
        ],
    )

    generator = MarimoIslandGenerator._from_ir(notebook)

    rendered = [stub.render() for stub in generator.stubs]
    assert all('data-reactive="false"' in html for html in rendered)
    assert "x%20%2B%201" not in rendered[1]

    await generator.build()

    assert generator.stubs[0].output is None
    assert generator.stubs[1].output is None


def test_render_head():
    generator = MarimoIslandGenerator()
    head_html = generator.render_head()

    assert (
        '<script type="module" src="https://cdn.jsdelivr.net/npm/@marimo-team/islands@'
        in head_html
    )
    assert (
        'href="https://cdn.jsdelivr.net/npm/@marimo-team/islands@' in head_html
    )
    assert (
        '<link rel="preconnect" href="https://fonts.googleapis.com" />'
        in head_html
    )
    assert 'href="https://cdn.jsdelivr.net/npm/katex@' in head_html

    snapshot("header.txt", head_html.replace(__version__, "0.0.0"))


def test_render_init_island():
    generator = MarimoIslandGenerator()
    init_island = generator.render_init_island()

    assert "<marimo-island" in init_island
    assert 'data-reactive="false"' in init_island
    assert "Initializing..." in init_island


def test_render_body():
    generator = MarimoIslandGenerator()
    generator.add_code("import marimo as mo")
    generator.add_code("mo.md('Hello, World!')")

    body_html = generator.render_body()

    assert "<marimo-island" in body_html
    assert 'data-reactive="true"' in body_html
    assert "Hello%2C%20World!" in body_html
    assert "Initializing..." in body_html  # Check for init island

    # Test without init island
    body_html_no_init = generator.render_body(include_init_island=False)
    assert "Initializing..." not in body_html_no_init


async def test_render_html():
    generator = MarimoIslandGenerator()
    generator.add_code("import marimo as mo")
    generator.add_code("mo.md('Hello, HTML!')")

    html = generator.render_html()

    assert "<!doctype html>" in html
    assert '<html lang="en">' in html
    assert "<head>" in html
    assert "<body>" in html
    assert "Hello%2C%20HTML!" in html
    snapshot("html.txt", html.replace(__version__, "0.0.0"))


def test_app_config():
    generator = MarimoIslandGenerator()
    generator._config = _AppConfig(width="medium", app_title="Test App")

    body_html = generator.render_body()
    assert 'style="margin: auto; max-width: 1110px;"' in body_html

    html = generator.render_html()
    assert "<title> Test App </title>" in html
