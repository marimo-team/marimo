# Copyright 2023 Marimo. All rights reserved.
"""marimo backend for matplotlib

Adapted from

matplotlib/matplotlib/blob/main/lib/matplotlib/backends/backend_template.py

and

https://stackoverflow.com/questions/58153024/matplotlib-how-to-create-original-backend
"""
from __future__ import annotations

import base64
import io
from typing import Optional

import matplotlib.pyplot as plt  # type: ignore
from matplotlib.backend_bases import FigureManagerBase, Gcf  # type: ignore
from matplotlib.backends.backend_agg import FigureCanvasAgg  # type: ignore

from marimo._messaging.ops import CellOp
from marimo._output.utils import build_data_url

FigureCanvas = FigureCanvasAgg


def close_figures() -> None:
    if Gcf.get_all_fig_managers():
        plt.close("all")


def _internal_show(canvas: FigureCanvasAgg) -> None:
    buf = io.BytesIO()
    buf.seek(0)
    canvas.figure.savefig(buf, format="png")
    plt.close(canvas.figure)
    mimetype = "image/png"
    plot_bytes = base64.b64encode(buf.getvalue())
    CellOp.broadcast_console_output(
        channel="media",
        mimetype=mimetype,
        data=build_data_url(mimetype=mimetype, data=plot_bytes),
        cell_id=None,
        status=None,
    )


class FigureManager(FigureManagerBase):  # type: ignore
    def show(self) -> None:
        _internal_show(self.canvas)


def show(*, block: Optional[bool] = None) -> None:
    del block
    for manager in Gcf.get_all_fig_managers():
        _internal_show(manager.canvas)
