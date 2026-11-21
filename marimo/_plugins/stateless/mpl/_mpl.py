# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._output.rich_help import mddoc
from marimo._utils.deprecated import deprecated

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure, SubFigure

    from marimo._output.hypertext import Html


@mddoc
@deprecated(
    "mo.mpl.interactive is deprecated. Use "
    "mo.ui.matplotlib(figure, brush=False, pan=True, zoom=True) instead."
)
def interactive(figure: Figure | SubFigure | Axes) -> Html:
    """Display a Matplotlib plot with pan and zoom.

    Deprecated. Use `mo.ui.matplotlib(figure, brush=False, pan=True, zoom=True)`.
    """
    from marimo._plugins.ui._impl.mpl import matplotlib

    return matplotlib(figure, brush=False, pan=True, zoom=True)
