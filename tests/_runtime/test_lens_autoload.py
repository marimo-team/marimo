# Copyright 2026 Marimo. All rights reserved.
import gc
import sys
import weakref
from importlib.machinery import ModuleSpec
from types import ModuleType
from unittest.mock import Mock, patch

import pytest

from marimo._runtime.commands import ExecuteCellCommand
from tests._runtime._helpers.session import mocked_kernel_session


class Lens:
    def _repr_html_(self):
        return "<span>Lens</span>"


def _lens_module(automatic_lens=None) -> ModuleType:
    module = ModuleType("marimo_lens")
    module.__spec__ = ModuleSpec("marimo_lens", loader=None)
    if automatic_lens is not None:
        module.automatic_lens = automatic_lens
    return module


def _outputs(session, cell_id):
    return [
        op.output.data
        for op in session.streams.stream.cell_notifications
        if op.cell_id == cell_id and op.output is not None
    ]


@pytest.mark.parametrize("expression", ["", "mo.md('hello')"])
async def test_lens_shows_the_automatic_lens_after_the_marimo_import(
    expression,
):
    automatic_lens = Mock(side_effect=Lens)
    with mocked_kernel_session() as session:
        kernel = session.kernel
        command = ExecuteCellCommand(
            cell_id="lens", code=f"import marimo as mo\n{expression}"
        )
        with patch.dict(sys.modules, marimo_lens=_lens_module(automatic_lens)):
            await kernel.run([command])
            assert not kernel.errors
            first_lens = kernel.graph.cells["lens"].output[1]
            assert isinstance(first_lens, Lens)
            if expression:
                assert "hello" in _outputs(session, "lens")[-1]
            assert "<span>Lens</span>" in _outputs(session, "lens")[-1]

            await kernel.run([command])
            assert kernel.graph.cells["lens"].output[1] is not first_lens

            await kernel.run(
                [ExecuteCellCommand(cell_id="other", code="mo.md('other')")]
            )
        assert kernel.graph.cells["other"].output is None
        assert automatic_lens.call_count == 2


async def test_lens_keeps_the_cell_output_when_lens_declines():
    automatic_lens = Mock(return_value=None)
    with mocked_kernel_session() as session:
        with patch.dict(sys.modules, marimo_lens=_lens_module(automatic_lens)):
            await session.kernel.run(
                [
                    ExecuteCellCommand(
                        cell_id="lens",
                        code="import marimo as mo\nmo.md('original')",
                    )
                ]
            )
        output = _outputs(session, "lens")[-1]
        assert "original" in output
        assert "<span>Lens</span>" not in output
        automatic_lens.assert_called_once_with()


@pytest.mark.parametrize("installed", [False, True])
async def test_lens_absent(installed):
    # An installed module without automatic_lens is an older marimo-lens.
    module = _lens_module() if installed else None
    with mocked_kernel_session() as session:
        with (
            patch.dict(sys.modules, marimo_lens=module),
            patch(
                "marimo._runtime.runner.hooks_lens.LOGGER.warning"
            ) as warning,
        ):
            await session.kernel.run(
                [
                    ExecuteCellCommand(
                        cell_id="lens", code="import marimo as mo"
                    )
                ]
            )
        assert not session.kernel.errors
        assert session.kernel.graph.cells["lens"].output is None
        warning.assert_not_called()


@pytest.mark.parametrize("failure", ["dependency", "automatic_lens"])
async def test_broken_lens_does_not_interrupt_notebook(failure):
    broken_lens = _lens_module()
    if failure == "dependency":
        broken_lens.__getattr__ = Mock(
            side_effect=ModuleNotFoundError(name="anywidget")
        )
    else:
        broken_lens.automatic_lens = Mock(
            side_effect=RuntimeError("broken Lens")
        )

    with mocked_kernel_session() as session:
        with (
            patch.dict(sys.modules, marimo_lens=broken_lens),
            patch(
                "marimo._runtime.runner.hooks_lens.LOGGER.warning"
            ) as warning,
        ):
            await session.kernel.run(
                [
                    ExecuteCellCommand(
                        cell_id="import",
                        code="import marimo as mo\nmo.md('original output')",
                    ),
                    ExecuteCellCommand(
                        cell_id="dependent",
                        code="answer = mo.md('still runs')",
                    ),
                ]
            )
        assert not session.kernel.errors
        assert "answer" in session.kernel.globals
        assert "original output" in _outputs(session, "import")[-1]
        warning.assert_called_once()


async def test_lens_lifetime_preserves_cell_output():
    from marimo._plugins.ui._core.ui_element import UIElement

    instances = []

    def automatic_lens():
        lens = Lens()
        instances.append(weakref.ref(lens))
        return lens

    with mocked_kernel_session() as session:
        with patch.dict(sys.modules, marimo_lens=_lens_module(automatic_lens)):
            await session.kernel.run(
                [
                    ExecuteCellCommand(
                        cell_id="lens",
                        code="import marimo as mo\nmo.ui.button()",
                    )
                ]
            )
        gc.collect()
        assert instances[0]() is not None
        cell = session.kernel.graph.cells["lens"]
        assert isinstance(cell.output[0], UIElement)
        previous_output = weakref.ref(cell.output[0])

        await session.kernel.run(
            [ExecuteCellCommand(cell_id="lens", code="1")]
        )
        gc.collect()
        assert instances[0]() is None
        assert previous_output() is None


async def test_installed_lens_keeps_one_lens_per_notebook():
    marimo_lens = pytest.importorskip("marimo_lens")
    with mocked_kernel_session() as session:
        kernel = session.kernel
        await kernel.run(
            [
                ExecuteCellCommand(
                    cell_id="first", code="import marimo as mo"
                ),
                ExecuteCellCommand(
                    cell_id="second", code="import marimo as other_mo"
                ),
            ]
        )
        automatic = kernel.graph.cells["first"].output[1]
        assert isinstance(automatic, marimo_lens.Lens)
        assert kernel.graph.cells["second"].output is None
        assert marimo_lens.notebook_lens() is automatic

        await kernel.run(
            [
                ExecuteCellCommand(
                    cell_id="authored",
                    code="from marimo_lens import Lens\n"
                    "lens = Lens(dom_selector='main')",
                )
            ]
        )
        assert not kernel.errors
        assert marimo_lens.notebook_lens() is kernel.globals["lens"]


async def test_installed_lens_stays_out_of_apps():
    marimo_lens = pytest.importorskip("marimo_lens")
    from marimo._session.model import SessionMode

    with mocked_kernel_session(mode=SessionMode.RUN) as session:
        await session.kernel.run(
            [ExecuteCellCommand(cell_id="app", code="import marimo as mo")]
        )
        assert not session.kernel.errors
        assert session.kernel.graph.cells["app"].output is None
        assert marimo_lens.notebook_lens() is None
