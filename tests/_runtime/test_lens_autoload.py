# Copyright 2026 Marimo. All rights reserved.
import sys
from unittest.mock import patch

import pytest

from marimo._runtime.commands import ExecuteCellCommand
from tests._runtime._helpers.session import mocked_kernel_session


@pytest.mark.parametrize("expression", ["", "mo.md('hello')"])
async def test_lens_mount_and_rerun(expression):
    lens = pytest.importorskip("marimo_lens")
    with mocked_kernel_session() as session:
        kernel = session.kernel
        command = ExecuteCellCommand(
            cell_id="lens", code=f"import marimo as mo\n{expression}"
        )
        await kernel.run([command])
        assert not kernel.errors
        first_lens = kernel.graph.cells["lens"].output[1]
        assert isinstance(first_lens, lens.Lens)
        outputs = [
            op.output.data
            for op in session.streams.stream.cell_notifications
            if op.cell_id == "lens" and op.output is not None
        ]
        if expression:
            assert "hello" in outputs[-1]
        assert "marimo-anywidget" in outputs[-1]
        await kernel.run([command])
        assert not kernel.errors
        assert kernel.graph.cells["lens"].output[1] is not first_lens
        await kernel.run(
            [ExecuteCellCommand(cell_id="other", code="mo.md('other')")]
        )
        assert kernel.graph.cells["other"].output is None


async def test_lens_absent():
    with mocked_kernel_session() as session:
        with (
            patch.dict(sys.modules, marimo_lens=None),
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
        warning.assert_not_called()


@pytest.mark.parametrize(
    "failure",
    ["import", "dependency", "constructor", "constructor_missing_module"],
)
async def test_broken_lens_does_not_interrupt_notebook(failure):
    import sys
    from importlib.machinery import ModuleSpec
    from types import ModuleType
    from unittest.mock import Mock

    broken_lens = ModuleType("marimo_lens")
    broken_lens.__spec__ = ModuleSpec("marimo_lens", loader=None)
    if failure == "dependency":
        broken_lens.__getattr__ = Mock(
            side_effect=ModuleNotFoundError(name="anywidget")
        )
    elif failure in {"constructor", "constructor_missing_module"}:

        class BrokenLens:
            def __init__(self):
                if failure == "constructor":
                    raise RuntimeError("broken Lens")
                raise ModuleNotFoundError(name="marimo_lens")

        broken_lens.Lens = BrokenLens

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
        outputs = [
            op.output.data
            for op in session.streams.stream.cell_notifications
            if op.cell_id == "import" and op.output is not None
        ]
        assert "original output" in outputs[-1]
        warning.assert_called_once()


async def test_lens_lifetime_preserves_cell_output():
    import gc
    import sys
    import weakref
    from importlib.machinery import ModuleSpec
    from types import ModuleType

    from marimo._plugins.ui._core.ui_element import UIElement

    instances = []

    class Lens:
        def __init__(self):
            instances.append(weakref.ref(self))

        def _repr_html_(self):
            return "<span>Lens</span>"

    module = ModuleType("marimo_lens")
    module.__spec__ = ModuleSpec("marimo_lens", loader=None)
    module.Lens = Lens

    with mocked_kernel_session() as session:
        with patch.dict(sys.modules, marimo_lens=module):
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


async def test_lens_mounts_once_per_notebook():
    lens = pytest.importorskip("marimo_lens")
    from marimo._runtime.commands import DeleteCellCommand

    # Separate kernels must each mount their own Lens.
    for _ in range(2):
        with mocked_kernel_session() as session:
            kernel = session.kernel
            first = ExecuteCellCommand(
                cell_id="first", code="import marimo as mo"
            )
            second = ExecuteCellCommand(
                cell_id="second", code="import marimo as other_mo"
            )
            await kernel.run([first])
            mounted = kernel.graph.cells["first"].output[1]
            assert isinstance(mounted, lens.Lens)

            await kernel.run([second])
            await kernel.run([second])
            assert kernel.graph.cells["second"].output is None
            assert kernel.graph.cells["first"].output[1] is mounted

            await kernel.delete_cell(DeleteCellCommand(cell_id="first"))
            await kernel.run([second])
            replacement = kernel.graph.cells["second"].output[1]
            assert isinstance(replacement, lens.Lens)
            assert replacement is not mounted
            assert not kernel.errors
