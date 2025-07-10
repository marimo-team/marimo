from __future__ import annotations

from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.hypertext import Html
from marimo._runtime.requests import DeleteCellRequest
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


@pytest.mark.skipif(
    not DependencyManager.matplotlib.has(),
    reason="matplotlib is not installed",
)
async def test_mpl_interactive(k: Kernel, exec_req: ExecReqProvider) -> None:
    from threading import Thread

    # This tests that the interactive figure is correctly displayed
    # and does not crash when tornado is not installed.

    with patch.object(Thread, "start", lambda self: None):  # noqa: ARG005
        await k.run(
            [
                cell := exec_req.get(
                    """
                    # remove tornado from sys.modules
                    import sys
                    sys.modules.pop("tornado", None)

                    import marimo as mo
                    import matplotlib.pyplot as plt
                    plt.plot([1, 2])
                    try:
                        interactive = mo.mpl.interactive(plt.gcf())
                    except Exception as e:
                        interactive = str(e)
                    """
                ),
            ]
        )

        interactive = k.globals["interactive"]
        assert isinstance(interactive, Html)
        assert interactive.text.startswith("<iframe srcdoc=")
        await k.delete_cell(DeleteCellRequest(cell_id=cell.cell_id))


@pytest.mark.skipif(
    not DependencyManager.matplotlib.has(),
    reason="matplotlib is not installed",
)
async def test_mpl_show(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import matplotlib.pyplot as plt
                plt.plot([1, 2])
                plt.show()
                """
            )
        ]
    )


@pytest.mark.skipif(
    not DependencyManager.matplotlib.has(),
    reason="matplotlib is not installed",
)
def test_patch_javascript() -> None:
    from matplotlib.backends.backend_webagg_core import FigureManagerWebAgg

    from marimo._plugins.stateless.mpl._mpl import patch_javascript

    javascript: str = str(FigureManagerWebAgg.get_javascript())  # type: ignore[no-untyped-call]
    assert javascript is not None
    javascript = patch_javascript(javascript)
    assert javascript.count("// canvas.focus();") == 1
    assert javascript.count("// canvas_div.focus();") == 1
