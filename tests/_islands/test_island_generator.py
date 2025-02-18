from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo import __version__
from marimo._ast.app import _AppConfig
from marimo._islands._island_generator import (
    MarimoIslandGenerator,
)
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from pathlib import Path

snapshot = snapshotter(__file__)


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
