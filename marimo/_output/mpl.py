# Copyright 2026 Marimo. All rights reserved.
"""marimo backend for matplotlib

Adapted from

matplotlib/matplotlib/blob/main/lib/matplotlib/backends/backend_template.py

and

https://stackoverflow.com/questions/58153024/matplotlib-how-to-create-original-backend
"""

from __future__ import annotations

import base64
import io
import json
import struct
from typing import Optional

import matplotlib.pyplot as plt
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import (
    FigureCanvasBase,
    FigureManagerBase,
)
from matplotlib.backends.backend_agg import FigureCanvasAgg

from marimo._messaging.cell_output import CellChannel
from marimo._messaging.mimetypes import METADATA_KEY, KnownMimeType
from marimo._messaging.notification_utils import CellNotificationUtils
from marimo._utils.data_uri import build_data_url

FigureCanvas = FigureCanvasAgg


def close_figures() -> None:
    if Gcf.get_all_fig_managers():
        plt.close("all")


def _extract_png_dimensions(png_bytes: bytes) -> tuple[int, int]:
    """Extract width and height from PNG binary data.

    Args:
        png_bytes: Raw PNG file data

    Returns:
        Tuple of (width, height) in pixels
    """
    # Find IHDR chunk and extract dimensions
    ihdr_index = png_bytes.index(b"IHDR")
    # Next 8 bytes after IHDR are width (4 bytes) and height (4 bytes)
    width, height = struct.unpack(
        ">II", png_bytes[ihdr_index + 4 : ihdr_index + 12]
    )
    return width, height


def _render_figure_mimebundle(
    fig: FigureCanvasBase,
) -> tuple[KnownMimeType, str]:
    """Render a matplotlib figure as a mimebundle with retina support.

    Args:
        fig: Matplotlib figure canvas to render

    Returns:
        Tuple of (mimetype, json_data) where json_data is a mimebundle
        containing the PNG data URL and display metadata
    """
    buf = io.BytesIO()

    # Get current DPI and double it for retina display (like Jupyter)
    original_dpi = fig.figure.dpi  # type: ignore[attr-defined]
    retina_dpi = original_dpi * 2

    fig.figure.savefig(buf, format="png", bbox_inches="tight", dpi=retina_dpi)  # type: ignore[attr-defined]

    png_bytes = buf.getvalue()
    plot_bytes = base64.b64encode(png_bytes)

    image_mimetype: KnownMimeType = "image/png"
    data_url = build_data_url(mimetype=image_mimetype, data=plot_bytes)

    try:
        # Extract dimensions from the PNG
        width, height = _extract_png_dimensions(png_bytes)
        mimebundle = {
            "image/png": data_url,
            METADATA_KEY: {
                "image/png": {
                    "width": width // 2,
                    "height": height // 2,
                }
            },
        }
        return (
            "application/vnd.marimo+mimebundle",
            json.dumps(mimebundle),
        )
    except (ValueError, struct.error, IndexError):
        # Fall back to plain image if dimension extraction fails
        return (image_mimetype, data_url)


def _internal_show(canvas: FigureCanvasBase) -> None:
    mimetype, data = _render_figure_mimebundle(canvas)
    plt.close(canvas.figure)
    CellNotificationUtils.broadcast_console_output(
        channel=CellChannel.MEDIA,
        mimetype=mimetype,
        data=data,
        cell_id=None,
        status=None,
    )


class FigureManager(FigureManagerBase):
    def show(self) -> None:
        _internal_show(self.canvas)


def show(*, block: Optional[bool] = None) -> None:
    del block
    for manager in Gcf.get_all_fig_managers():
        _internal_show(manager.canvas)
