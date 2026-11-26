from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def marimo_mpl_backend() -> Iterator[None]:
    matplotlib = pytest.importorskip("matplotlib")
    backend = matplotlib.get_backend()
    # Imports outside a notebook can leave the native GUI backend active.
    matplotlib.use("module://marimo._output.mpl")
    try:
        yield
    finally:
        from matplotlib import pyplot as plt

        plt.close("all")
        matplotlib.use(backend)


@pytest.mark.parametrize("target", ["axes", "figure", "subfigure"])
def test_interactive_alias(target: str) -> None:
    pytest.importorskip("matplotlib.backends.backend_anywidget")
    from matplotlib.figure import Figure

    import marimo as mo

    fig = Figure()
    sub = fig.subfigures(1, 1)
    ax = sub.subplots()
    obj = {"axes": ax, "figure": fig, "subfigure": sub}[target]
    with pytest.warns(DeprecationWarning, match=r"mo\.ui\.matplotlib"):
        plot = mo.mpl.interactive(figure=obj)
    assert isinstance(plot, mo.ui.matplotlib)
    assert plot.axes is obj
    widget = plot._plot_widget
    assert widget is not None
    assert widget.options["brush"] is False
    assert widget.options["pan"] is True
    assert widget.options["zoom"] is True


def test_interactive_alias_exports_png(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64

    from matplotlib.figure import Figure

    import marimo as mo

    monkeypatch.setenv("MARIMO_NO_JS", "true")
    fig = Figure()
    fig.subplots().plot([0, 1], [1, 0])
    with pytest.warns(DeprecationWarning, match=r"mo\.ui\.matplotlib"):
        mime, uri = mo.mpl.interactive(fig)._mime_()
    assert mime == "image/png"
    assert base64.b64decode(uri.split(",", 1)[1]).startswith(b"\x89PNG")


@pytest.mark.requires("matplotlib")
async def test_mpl_show(k: Kernel, exec_req: ExecReqProvider) -> None:
    from marimo._output.mpl import _internal_show

    with patch(
        "marimo._output.mpl._internal_show", wraps=_internal_show
    ) as show:
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

    assert not k.errors
    show.assert_called_once()
