from __future__ import annotations

import pytest

from marimo import __version__
from marimo._islands.island_generator import MarimoIslandGenerator
from tests.mocks import snapshotter

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
    generator.add_code("import marimo as mo")
    generator.add_code("mo.md('Hello, islands!')")

    # Check if render raises an error when build() is not called
    with pytest.raises(ValueError):
        generator.render("mo.md('Hello, islands!')")

    await generator.build()

    # Check if render works after build() is called
    snapshot("island.txt", generator.render("mo.md('Hello, islands!')"))

    # Check if render returns an empty string for a non-existent cell
    assert generator.render("mo.md('Non-existent cell')") == ""


async def test_render_header():
    generator = MarimoIslandGenerator()
    generator.add_code("print('Hello, islands!')")
    await generator.build()

    # Check if render_header works after build() is called
    snapshot(
        "header.txt", generator.render_header().replace(__version__, "0.0.0")
    )
