# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import functools
import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union
from uuid import uuid4

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._plugins.stateless.mpl._mpl import (
    css_content,
    new_figure_manager_given_figure,
    patch_javascript,
    png_bytes,
)
from marimo._plugins.ui._core.ui_element import InitializationArgs, UIElement
from marimo._plugins.ui._impl.anywidget.init import WIDGET_COMM_MANAGER
from marimo._plugins.ui._impl.comm import MarimoComm
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._runtime.context import RuntimeContext
from marimo._runtime.virtual_file.virtual_file import VirtualFile
from marimo._types.ids import WidgetModelId

if TYPE_CHECKING:
    from matplotlib.figure import Figure, SubFigure

LOGGER = _loggers.marimo_logger()


class _SyncWebSocket:
    """Adapter passed to FigureManagerWebAgg.add_web_socket().

    Translates send_json/send_binary calls into MarimoComm messages
    that travel through the model-lifecycle notification channel.
    """

    def __init__(self, comm: MarimoComm) -> None:
        self._comm = comm

    def send_json(self, content: Any) -> None:
        self._comm.send(
            data={
                "method": "custom",
                "content": {"type": "json", "data": content},
            },
        )

    def send_binary(self, blob: bytes) -> None:
        self._comm.send(
            data={
                "method": "custom",
                "content": {"type": "binary"},
            },
            buffers=[blob],
        )


def _get_mpl_css() -> str:
    """Collect all matplotlib WebAgg CSS files and our custom CSS."""
    from matplotlib.backends.backend_webagg_core import (
        FigureManagerWebAgg,
    )

    static_path = Path(
        FigureManagerWebAgg.get_static_file_path()  # type: ignore[no-untyped-call]
    )
    parts: list[str] = []
    for css_file in sorted(static_path.glob("css/*.css")):
        parts.append(css_file.read_text())
    # Our own overrides
    parts.append(css_content)
    return "\n".join(parts)


@functools.lru_cache(maxsize=1)
def _get_mpl_css_vfile() -> VirtualFile:
    """Get or create a cached virtual file for the combined CSS."""
    return VirtualFile.create_and_register(
        _get_mpl_css().encode("utf-8"), "css"
    )


@functools.lru_cache(maxsize=1)
def _get_toolbar_images() -> dict[str, str]:
    """Return a dict of {filename: data-URI} for all toolbar PNGs."""
    import matplotlib as mpl

    img_dir = Path(mpl.get_data_path(), "images")
    images: dict[str, str] = {}
    for png in img_dir.glob("*.png"):
        data = base64.b64encode(png.read_bytes()).decode("ascii")
        images[png.stem] = f"data:image/png;base64,{data}"
    return images


def _get_patched_mpl_js() -> str:
    """Get the mpl.js source with focus-stealing patches applied."""
    from matplotlib.backends.backend_webagg_core import (
        FigureManagerWebAgg,
    )

    return patch_javascript(
        FigureManagerWebAgg.get_javascript()  # type: ignore[no-untyped-call]
    )


@functools.lru_cache(maxsize=1)
def _get_mpl_js_vfile() -> VirtualFile:
    """Get or create a cached virtual file for the patched mpl.js."""
    return VirtualFile.create_and_register(
        _get_patched_mpl_js().encode("utf-8"), "js"
    )


class ModelIdRef(dict):  # type: ignore[type-arg]
    """Wire-format value: just a model_id reference."""

    pass


class mpl_interactive(UIElement[ModelIdRef, dict[str, Any]]):
    """UIElement wrapping an interactive matplotlib figure.

    Uses MarimoComm for bidirectional communication instead of a
    separate WebSocket server, enabling support in WASM/Pyodide.
    """

    def __init__(self, figure: Union[Figure, SubFigure]) -> None:
        self._figure = figure

        # Create FigureManagerWebAgg
        self._figure_manager = new_figure_manager_given_figure(
            id(figure), figure
        )

        # Get figure dimensions in CSS pixels for initial sizing.
        # The logical DPI from rcParams gives the CSS pixel size that
        # mpl.js expects before device_pixel_ratio adjustment.
        import matplotlib

        logical_dpi = matplotlib.rcParams["figure.dpi"]
        w_in, h_in = figure.get_size_inches()
        css_w = int(w_in * logical_dpi)
        css_h = int(h_in * logical_dpi)

        # Generate a model id for the comm
        model_id = WidgetModelId(uuid4().hex)

        # Create the MarimoComm
        self._comm = MarimoComm(
            comm_id=model_id,
            comm_manager=WIDGET_COMM_MANAGER,
            target_name="marimo.mpl_interactive",
            data={"state": {}, "method": "open"},
        )

        # Register message handler: frontend → backend
        self._comm.on_msg(self._handle_comm_msg)

        # Create the SyncWebSocket adapter
        self._sync_ws = _SyncWebSocket(self._comm)

        # Connect the websocket to the figure manager
        self._figure_manager.add_web_socket(self._sync_ws)  # type: ignore[no-untyped-call]

        super().__init__(
            component_name="marimo-mpl-interactive",
            initial_value=ModelIdRef(model_id=model_id),
            label=None,
            args={
                "mpl-js-url": _get_mpl_js_vfile().url,
                "css-url": _get_mpl_css_vfile().url,
                "toolbar-images": _get_toolbar_images(),
                "width": css_w,
                "height": css_h,
            },
            on_change=None,
        )

    def _initialize(
        self,
        initialization_args: InitializationArgs[ModelIdRef, dict[str, Any]],
    ) -> None:
        super()._initialize(initialization_args)
        # Link the comm to this UIElement for proper lifecycle
        self._comm.ui_element_id = self._id

        # Register cleanup so the comm is closed and the
        # figure manager is cleaned up on cell re-run
        from marimo._runtime.context import (
            ContextNotInitializedError,
            get_context,
        )

        try:
            ctx = get_context()
            ctx.cell_lifecycle_registry.add(_MplCleanupHandle(self._comm))
        except ContextNotInitializedError:
            pass

    def _handle_comm_msg(self, msg: dict[str, Any]) -> None:
        """Handle messages from frontend → backend.

        The comm payload structure from ModelCommand.into_comm_payload() is:
          {"content": {"data": {"method": "custom", "content": <mpl_event>}},
           "buffers": [...]}

        The actual mpl event (with "type" key) is at
          msg["content"]["data"]["content"].
        """
        content = msg.get("content", {})
        data = content.get("data", {})
        # For custom messages, the actual payload is nested under "content"
        event = data.get("content", data)

        msg_type = event.get("type")
        if msg_type == "supports_binary":
            # Acknowledgement, no action needed
            return
        elif msg_type == "download":
            # Handle download request
            fmt = event.get("format", "png")
            self._handle_download(fmt)
            return
        else:
            # Forward to figure manager (mouse events, toolbar actions, etc.)
            self._figure_manager.handle_json(event)  # type: ignore[no-untyped-call]

    def _handle_download(self, fmt: str) -> None:
        """Render figure to the requested format and send back via comm."""
        buf = io.BytesIO()
        self._figure_manager.canvas.figure.savefig(
            buf, format=fmt, bbox_inches="tight"
        )
        blob = buf.getvalue()
        self._comm.send(
            data={
                "method": "custom",
                "content": {"type": "download", "format": fmt},
            },
            buffers=[blob],
        )

    def _convert_value(
        self, value: ModelIdRef | dict[str, Any]
    ) -> dict[str, Any]:
        del value
        return {}

    def _repr_png_(self) -> bytes:
        """PNG fallback for ipynb export."""
        return png_bytes(self._figure)

    def _mime_(self) -> tuple[KnownMimeType, str]:
        return super()._mime_()


class _MplCleanupHandle(CellLifecycleItem):
    """Closes the MarimoComm when the cell is re-run or deleted."""

    def __init__(self, comm: MarimoComm) -> None:
        self._comm = comm

    def create(self, context: RuntimeContext) -> None:
        del context

    def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
        del context, deletion
        self._comm.close()
        return True
