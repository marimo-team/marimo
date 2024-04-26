from __future__ import annotations

import pytest

from marimo import __version__
from marimo._islands.island_generator import (
    MarimoIslandGenerator,
    handle_mimetypes,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
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
    block1 = generator.add_code("import marimo as mo")
    block2 = generator.add_code("mo.md('Hello, islands!')")

    # Check if render raises an error when build() is not called
    with pytest.raises(AssertionError) as e:
        block1.render()
    assert "You must call build() before rendering" in str(e.value)

    with pytest.raises(AssertionError) as e:
        block2.render(include_code=False)
    assert "You must call build() before rendering" in str(e.value)

    await generator.build()

    with pytest.raises(ValueError) as e:
        block1.render(include_code=False, include_output=False)
    assert str(e.value) == "You must include either code or output"

    # Check if render works after build() is called
    snapshot("island.txt", block2.render())

    snapshot("island-no-code.txt", block2.render(include_code=False))

    snapshot("island-no-output.txt", block2.render(include_output=False))


async def test_render_head():
    generator = MarimoIslandGenerator()
    generator.add_code("print('Hello, islands!')")
    await generator.build()

    # Check if render_head works after build() is called
    snapshot(
        "header.txt", generator.render_head().replace(__version__, "0.0.0")
    )


async def test_handle_image_mimetype():
    small_image = CellOutput(
        data="data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==",
        mimetype="image/gif",
        channel=CellChannel.OUTPUT,
    )
    assert handle_mimetypes(small_image).startswith("<img")


async def test_handle_json_mimetype():
    small_image = CellOutput(
        data="[1, 2, 3]",
        mimetype="application/json",
        channel=CellChannel.OUTPUT,
    )
    assert handle_mimetypes(small_image).startswith("<marimo-json")
