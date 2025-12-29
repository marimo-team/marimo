# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import sys
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Optional,
    TypeVar,
    cast,
)

from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import InitializationArgs, UIElement
from marimo._plugins.ui._impl.comm import MarimoComm, MarimoCommManager
from marimo._runtime.functions import Function
from marimo._types.ids import WidgetModelId

if TYPE_CHECKING:
    from panel.viewable import Viewable

LOGGER = _loggers.marimo_logger()

COMM_MANAGER = MarimoCommManager()

comm_class: Optional[type[Any]] = None
loaded_extension: int = 0
loaded_extensions: list[str] = []

T = TypeVar("T", bound=dict[str, Any])


@dataclass
class SendToWidgetArgs:
    message: Any
    buffers: Optional[list[Any]] = None


# Singleton, we only create one instance of this class
def _get_comm_class() -> type[Any]:
    global comm_class
    if comm_class:
        return comm_class

    from pyviz_comms import Comm  # type: ignore

    class MarimoPanelComm(Comm):  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, **kwargs)
            self._comm = MarimoComm(
                comm_id=WidgetModelId(str(self.id)),
                target_name="panel.comms",
                data={},
                comm_manager=COMM_MANAGER,
            )
            self._comm.on_msg(self._handle_msg)
            if self._on_open:
                self._on_open({})

        @classmethod
        def decode(cls, msg: SendToWidgetArgs) -> dict[str, Any]:
            buffers: dict[int, Any] = {
                i: memoryview(base64.b64decode(v))
                for i, v in enumerate(msg.buffers or [])
            }
            return dict(msg.message, _buffers=buffers)

        def send(
            self, data: Any = None, metadata: Any = None, buffers: Any = None
        ) -> None:
            buffers = buffers or []
            self.comm.send(
                {"content": data}, metadata=metadata, buffers=buffers
            )

    comm_class = MarimoPanelComm
    return comm_class


def render_extension(load_timeout: int = 500, loaded: bool = False) -> str:
    """
    Render Panel extension JavaScript.

    Args:
        load_timeout: Timeout for loading resources (in milliseconds)
        loaded: Whether the extension has been loaded before

    Returns:
        JavaScript code for Panel extension
    """
    # See panel.io.notebook.py
    from panel.config import panel_extension

    new_exts: list[str] = [
        ext
        for ext in panel_extension._loaded_extensions
        if ext not in loaded_extensions
    ]
    if loaded and not new_exts:
        return ""

    from bokeh.io.notebook import curstate  # type: ignore
    from bokeh.resources import CDN, INLINE
    from panel.config import config
    from panel.io.notebook import (  # type: ignore
        Resources,
        _autoload_js,
        bundle_resources,
        require_components,
        state,
    )
    from panel.io.resources import set_resource_mode  # type: ignore

    curstate().output_notebook()

    resources = INLINE if config.inline else CDN
    nb_endpoint = not state._is_pyodide
    with set_resource_mode(resources.mode):
        resources = Resources.from_bokeh(resources, notebook=nb_endpoint)  # type: ignore[no-untyped-call]
        bundle = bundle_resources(  # type: ignore[no-untyped-call]
            None,
            resources,
            notebook=nb_endpoint,
            reloading=loaded,
            enable_mathjax="auto",
        )
        configs, requirements, exports, skip_imports = require_components()  # type: ignore[no-untyped-call]
        ipywidget = "ipywidgets_bokeh" in sys.modules
        bokeh_js = _autoload_js(  # type: ignore[no-untyped-call]
            bundle=bundle,
            configs=configs,
            requirements=requirements,
            exports=exports,
            skip_imports=skip_imports,
            ipywidget=ipywidget,
            reloading=loaded,
            load_timeout=load_timeout,
        )
    loaded_extensions.extend(new_exts)
    return bokeh_js  # type: ignore[no-any-return]


def render_component(
    obj: Viewable,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Render a Panel component.

    Args:
        obj: Panel Viewable object

    Returns:
        Tuple containing reference ID, docs JSON, and render JSON
    """
    from bokeh.document import Document
    from bokeh.embed.util import standalone_docs_json_and_render_items
    from panel.io.model import add_to_doc

    doc = Document()
    comm = _get_comm_class()()
    root = obj._render_model(doc, comm)
    ref = root.ref["id"]
    obj._comms[ref] = (comm, comm)
    add_to_doc(root, doc, True)
    (docs_json, [render_item]) = standalone_docs_json_and_render_items(
        [root], suppress_callback_warning=True
    )
    render_json = render_item.to_json()
    return ref, docs_json, render_json  # type: ignore[return-value]


def _extract_holoviews_settings(obj: Any) -> dict[str, Any]:
    """
    Extract renderer settings from holoviews objects to pass to Panel.

    This ensures that settings like widget_location configured via hv.output()
    are respected when rendering holoviews objects through Panel.
    """
    try:
        import holoviews as hv  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        # Check if the object is a holoviews object
        if not isinstance(
            obj,
            (
                hv.core.ViewableElement,
                hv.core.Layout,
                hv.HoloMap,
                hv.DynamicMap,
                hv.core.spaces.HoloMap,
                hv.core.ndmapping.UniformNdMapping,
                hv.core.ndmapping.NdMapping,
            ),
        ):
            return {}

        # Get the current backend
        # Try to determine which backend is active
        backend = None
        if hasattr(hv.Store, "current_backend"):
            backend = hv.Store.current_backend
        elif hasattr(hv, "extension") and hasattr(
            hv.extension, "_loaded_backends"
        ):
            # Get the first loaded backend
            loaded_backends = list(hv.extension._loaded_backends.keys())
            if loaded_backends:
                backend = loaded_backends[0]

        if not backend:
            return {}

        # Get the renderer for the active backend
        try:
            renderer = hv.renderer(backend)
        except Exception:
            return {}

        # Extract relevant settings that Panel's HoloViews pane accepts
        panel_kwargs: dict[str, Any] = {}

        # widget_location is a common setting that affects widget placement
        if (
            hasattr(renderer, "widget_location")
            and renderer.widget_location is not None
        ):
            panel_kwargs["widget_location"] = renderer.widget_location

        # center is another setting that can be configured
        if hasattr(renderer, "center") and renderer.center is not None:
            panel_kwargs["center"] = renderer.center

        return panel_kwargs

    except ImportError:
        # holoviews is not installed
        return {}
    except Exception as e:
        # Log the error but don't fail - just don't apply settings
        LOGGER.debug(f"Failed to extract holoviews settings: {e}")
        return {}


@mddoc
class panel(UIElement[T, T]):
    """Create a UIElement from a Panel component.

    This proxies all the widget's attributes and methods, allowing seamless
    integration of Panel components with Marimo's UI system.

    Examples:
        ```python
        import marimo as mo
        import panel as pn

        slider = pn.widgets.IntSlider(start=0, end=10, value=5)
        rx_stars = mo.ui.panel(slider.rx() * "*")

        # In another cell, access its value
        # This works for all widgets
        slider.value
        ```

    Attributes:
        obj (Viewable): The widget being wrapped.

    Args:
        obj (Viewable): The widget to wrap.
    """

    def __init__(self, obj: Any):
        from panel.models.comm_manager import CommManager as PanelCommManager
        from panel.pane import panel as panel_func

        # Extract holoviews renderer settings if the object is a holoviews object
        panel_kwargs = _extract_holoviews_settings(obj)

        self.obj: Viewable = panel_func(obj, **panel_kwargs)  # type: ignore[assignment]
        # This gets set to True in super().__init__()
        self._initialized = False

        ref, docs_json, render_json = render_component(self.obj)
        self._ref = ref
        self._manager = PanelCommManager(plot_id=ref)  # type: ignore[no-untyped-call]

        global loaded_extension
        extension = render_extension(loaded=loaded_extension == id(self))
        if loaded_extension == 0:
            loaded_extension = id(self)

        super().__init__(
            component_name="marimo-panel",
            initial_value=cast(T, {}),
            label="",
            args={
                "extension": extension,
                "render_json": render_json,
                "docs_json": docs_json,
            },
            on_change=None,
            functions=(
                Function(
                    name="send_to_widget",
                    arg_cls=SendToWidgetArgs,
                    function=self._handle_msg,
                ),
            ),
        )

    def _handle_msg(self, msg: SendToWidgetArgs) -> None:
        ref = self._ref
        comm = self.obj._comms[ref][0]  # type: ignore[attr-defined]
        msg = comm.decode(msg)
        self.obj._on_msg(ref, self._manager, msg)  # type: ignore[attr-defined]
        comm.send(data={"type": "ACK"})

    def _initialize(
        self,
        initialization_args: InitializationArgs[T, T],
    ) -> None:
        super()._initialize(initialization_args)
        for comm, _ in self.obj._comms.values():  # type: ignore[attr-defined]
            if isinstance(comm.comm, MarimoComm):
                comm.comm.ui_element_id = self._id

    def _convert_value(self, value: T) -> T:
        return value

    # After the panel component has been initialized
    # forward all setattr to the component
    def __setattr__(self, name: str, value: Any) -> None:
        if self._initialized:
            # If the widget has the attribute, set it
            if hasattr(self.obj, name):
                return setattr(self.obj, name, value)
            return super().__setattr__(name, value)
        return super().__setattr__(name, value)

    # After the panel component has been initialized
    # forward all getattr to the component
    def __getattr__(self, name: str) -> Any:
        if name in ("widget", "_initialized"):
            try:
                return self.__getattribute__(name)
            except AttributeError:
                return None
        return getattr(self.obj, name)
