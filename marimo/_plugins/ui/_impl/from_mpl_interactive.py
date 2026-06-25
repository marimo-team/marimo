# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import functools
import io
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any
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
    from collections.abc import Callable

    from matplotlib.figure import Figure, SubFigure

LOGGER = _loggers.marimo_logger()


def _disconnect_owner_callbacks(canvas: Any, owner: Any) -> None:
    """Disconnect every callback on `canvas.callbacks` whose receiver is `owner`.

    `FigureCanvasBase.callbacks` is a property returning
    `figure._canvas_callbacks`, so every canvas bound to the same
    figure shares one registry. `NavigationToolbar2.__init__`
    registers `_zoom_pan_handler` (and a few siblings) on this
    shared registry; matplotlib has no public counterpart that
    disconnects them when a canvas/toolbar is discarded. Without this
    cleanup, every cell rerun would stack another toolbar's handler on
    the registry, leading to duplicate `press_pan`/`release_pan`
    dispatch.
    """
    registry = canvas.callbacks
    cids: list[int] = []
    for handlers in registry.callbacks.values():
        for cid, ref in handlers.items():
            fn = ref() if callable(ref) else ref
            if getattr(fn, "__self__", None) is owner:
                cids.append(cid)
    for cid in cids:
        registry.disconnect(cid)


class _FigureManagerRegistry:
    """Shared `FigureManagerWebAgg` per figure, reference-counted by live
    `mpl_interactive` instances.

    matplotlib assumes one canvas/manager per figure for the figure's
    lifetime, so every `mpl_interactive` wrapping the same figure reuses one
    manager (and thus one toolbar, zoom history, and shared callback
    registry). The manager is destroyed only when its last consumer is gone.

    Both maps are weak so neither pins a figure on its own:
      * The manager is held weakly; each live `mpl_interactive` keeps it alive
        via `self._figure_manager`, so the entry drops once all are disposed.
      * The figure is the weak key of the refcount map, so a discarded figure
        evicts its own count without manual cleanup.

    Bookkeeping only: manager creation, dpi/size capture, and canvas rebinding
    are matplotlib-specific and stay with the caller.
    """

    def __init__(self) -> None:
        self._managers: weakref.WeakValueDictionary[int, Any] = (
            weakref.WeakValueDictionary()
        )
        self._refcounts: weakref.WeakKeyDictionary[Any, int] = (
            weakref.WeakKeyDictionary()
        )
        # The figure's pristine dpi/size, captured before any interactive
        # resize, to restore when the shared manager is destroyed. Kept here
        # rather than on the manager so it shares the manager's lifecycle and
        # stays typed instead of stringly monkey-patched onto a foreign object.
        self._original_geometry: weakref.WeakKeyDictionary[
            Any, tuple[float, tuple[float, float]]
        ] = weakref.WeakKeyDictionary()

    def acquire(
        self, figure: Any, factory: Callable[[], Any]
    ) -> tuple[Any, bool]:
        """Return `(manager, created)` and increment the figure's refcount.

        Reuses the cached manager if present, otherwise builds one via
        `factory` and caches it. `created` is True only on the fresh build.
        """
        key = id(figure)
        manager = self._managers.get(key)
        created = False
        if manager is None:
            manager = factory()
            self._managers[key] = manager
            created = True
        self._refcounts[figure] = self._refcounts.get(figure, 0) + 1
        return manager, created

    def set_original_geometry(
        self, figure: Any, dpi: float, size_inches: tuple[float, float]
    ) -> None:
        self._original_geometry[figure] = (dpi, size_inches)

    def original_geometry(
        self, figure: Any
    ) -> tuple[float, tuple[float, float]] | None:
        return self._original_geometry.get(figure)

    def release(self, figure: Any) -> bool:
        """Decrement the figure's refcount.

        Returns True when it reaches zero (the caller destroys the manager),
        dropping every entry for the figure in that case.
        """
        count = self._refcounts.get(figure, 0) - 1
        if count > 0:
            self._refcounts[figure] = count
            return False
        self._refcounts.pop(figure, None)
        self._managers.pop(id(figure), None)
        self._original_geometry.pop(figure, None)
        return True


_FIGURE_MANAGERS = _FigureManagerRegistry()


# Must match the className on the container div in MplInteractivePlugin.tsx
_MPL_SCOPE = ".mpl-interactive-figure"


class _SyncWebSocket:
    """Adapter passed to FigureManagerWebAgg.add_web_socket().

    Translates send_json/send_binary calls into MarimoComm messages
    that travel through the model-lifecycle notification channel.

    Implements the interface expected by FigureManagerWebAgg:
    https://github.com/matplotlib/matplotlib/blob/9d83ca60096f313dfc9f144288501af18c770a4e/lib/matplotlib/backends/backend_webagg_core.py#L459
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
    """Collect safe matplotlib WebAgg CSS files and our custom CSS.

    We skip boilerplate.css and page.css because they contain global
    selectors (body, html, div, span, etc.) designed for a standalone
    page / iframe that would leak into the host page. Only mpl.css and
    fbm.css have properly scoped class-based selectors.

    All rules are wrapped inside a `.mpl-interactive-figure` scope so
    that any remaining broad selectors (e.g. `body`, `#figure`) do
    not leak into the host page when loaded as a `<link>` stylesheet.
    """
    from matplotlib.backends.backend_webagg_core import (
        FigureManagerWebAgg,
    )

    _SKIP = {"boilerplate.css", "page.css"}
    static_path = Path(
        FigureManagerWebAgg.get_static_file_path()  # type: ignore[no-untyped-call]
    )
    parts: list[str] = []
    for css_file in sorted(static_path.glob("css/*.css")):
        if css_file.name in _SKIP:
            continue
        parts.append(css_file.read_text())
    # Our own overrides
    parts.append(css_content)
    raw_css = "\n".join(parts)
    return _scope_css(raw_css, _MPL_SCOPE)


def _scope_css(css: str, scope: str) -> str:
    """Scope CSS rules using native CSS nesting.

    Wraps all rules inside a `<scope> { … }` block so that child
    selectors are implicitly prefixed.  This replaces the previous
    regex-based rewriter and correctly handles `@keyframes`,
    `@media`, and any other at-rules or complex selectors.

    Requires browser support for CSS Nesting (Chrome 120+, Firefox 117+,
    Safari 17.2+).
    """
    return f"{scope} {{\n{css}\n}}"


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


class mpl_interactive(UIElement[ModelIdRef, dict[str, Any]]):
    """UIElement wrapping an interactive matplotlib figure.

    Uses MarimoComm for bidirectional communication instead of a
    separate WebSocket server, enabling support in WASM/Pyodide.
    """

    def __init__(self, figure: Figure | SubFigure) -> None:
        self._figure = figure

        # SubFigure delegates dpi/size_inches to its parent Figure;
        # Figure.figure returns self, so this works for both.
        root = figure.figure
        self._original_dpi = root.get_dpi()
        self._original_size_inches = tuple(root.get_size_inches())

        # Reuse the figure's manager across reruns so toolbar state, zoom
        # history, and the shared callback registry survive. Only the comm is
        # recreated per element (below).
        manager, created = _FIGURE_MANAGERS.acquire(
            figure,
            lambda: new_figure_manager_given_figure(id(figure), figure),
        )
        if created:
            # Capture the pristine dpi/size once, before any interactive
            # resize mutates them; restored when the shared manager is
            # finally destroyed (refcount reaches zero).
            _FIGURE_MANAGERS.set_original_geometry(
                figure, self._original_dpi, self._original_size_inches
            )
        elif root.canvas is not manager.canvas:
            # matplotlib >= 3.11 resets `figure.canvas` to a bare
            # FigureCanvasBase on close, and marimo closes figures after every
            # cell run (`close_figures()` -> `plt.close("all")`). Re-bind the
            # cached canvas so the first frame after a rerun renders against it.
            root.set_canvas(manager.canvas)
        self._figure_manager = manager

        # Get figure dimensions in CSS pixels for initial sizing.
        # get_width_height() returns device pixels (includes DPI scaling).
        # Divide by the device-to-logical DPI ratio to get CSS pixels.
        import matplotlib

        w_px, h_px = self._figure_manager.canvas.get_width_height()
        logical_dpi: float = matplotlib.rcParams["figure.dpi"]
        actual_dpi: float = self._figure_manager.canvas.figure.dpi
        ratio = actual_dpi / logical_dpi if logical_dpi > 0 else 1
        css_w = int(w_px / ratio)
        css_h = int(h_px / ratio)

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
            ctx.cell_lifecycle_registry.add(
                _MplCleanupHandle(
                    comm=self._comm,
                    figure=self._figure,
                    figure_manager=self._figure_manager,
                    sync_ws=self._sync_ws,
                )
            )
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
        # matplotlib 3.11 resets `figure.canvas` to a bare FigureCanvasBase
        # when the figure is closed, and marimo closes figures after every
        # cell run (`close_figures()` -> `plt.close("all")`). Re-bind our
        # canvas so matplotlib's hit-testing (`Artist.contains` ->
        # `_different_canvas`) keeps accepting events and pan/zoom survive.
        canvas = self._figure_manager.canvas
        root_figure = canvas.figure.figure
        if root_figure.canvas is not canvas:
            root_figure.set_canvas(canvas)

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
            # Forward to figure manager (mouse events, toolbar actions, etc.).
            # Swallow callback exceptions so a buggy handler can't kill the
            # kernel subprocess; the exception propagates up through the comm
            # manager and terminates asyncio.run otherwise.
            try:
                self._figure_manager.handle_json(event)  # type: ignore[no-untyped-call]
            except Exception:
                LOGGER.exception(
                    "mpl_interactive handle_json failed for event type %s",
                    msg_type,
                )

    def _handle_download(self, fmt: str) -> None:
        """Render figure to the requested format and send back via comm."""
        try:
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
        except Exception:
            LOGGER.exception("mpl_interactive download failed (fmt=%s)", fmt)

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
    """Cleans up an `mpl_interactive` on cell re-run or deletion.

    The comm and websocket are per-element and always torn down. The figure
    manager is shared across every element wrapping the same figure, so it is
    destroyed only when the last of those elements is disposed (its refcount
    reaches zero). Callers that do not pass a `figure` fall back to destroying
    the manager unconditionally.
    """

    def __init__(
        self,
        comm: MarimoComm,
        figure: Any = None,
        figure_manager: Any = None,
        sync_ws: Any = None,
        original_dpi: float | None = None,
        original_size_inches: tuple[float, float] | None = None,
    ) -> None:
        self._comm = comm
        self._figure = figure
        self._figure_manager = figure_manager
        self._sync_ws = sync_ws
        self._original_dpi = original_dpi
        self._original_size_inches = original_size_inches

    def create(self, context: RuntimeContext) -> None:
        del context

    def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
        del context, deletion
        fm = self._figure_manager
        if fm is not None and self._sync_ws is not None:
            try:
                fm.remove_web_socket(self._sync_ws)
            except Exception:
                LOGGER.exception("Failed to remove mpl web socket")

        if self._figure is None:
            # No shared refcount (manual/legacy callers): destroy immediately,
            # restoring the geometry passed at construction.
            self._destroy_manager(
                self._original_dpi, self._original_size_inches
            )
        else:
            # Read the captured geometry before release drops it.
            geometry = _FIGURE_MANAGERS.original_geometry(self._figure)
            if _FIGURE_MANAGERS.release(self._figure):
                dpi, size = geometry if geometry is not None else (None, None)
                self._destroy_manager(dpi, size)

        self._comm.close()
        return True

    def _destroy_manager(
        self,
        dpi: float | None,
        size_inches: tuple[float, float] | None,
    ) -> None:
        fm = self._figure_manager
        if fm is None:
            return

        canvas = fm.canvas
        toolbar = getattr(canvas, "toolbar", None)
        if toolbar is not None:
            try:
                _disconnect_owner_callbacks(canvas, toolbar)
            except Exception:
                LOGGER.exception("Failed to disconnect mpl toolbar callbacks")

        if dpi is not None and size_inches is not None:
            try:
                # get the root figure (in case of Subfigure) which handles dpi
                root = canvas.figure.figure
                root.set_dpi(dpi)
                root.set_size_inches(*size_inches)
            except Exception:
                LOGGER.exception(
                    "Failed to restore mpl figure dpi/size on dispose"
                )
