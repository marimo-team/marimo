# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys
import weakref
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, Optional

from marimo import _loggers
from marimo._output.rich_help import mddoc
from marimo._plugins.ui._core.ui_element import InitializationArgs, UIElement
from marimo._plugins.ui._impl.comm import MarimoComm, MarimoCommManager
from marimo._runtime.functions import Function
from pyviz_comms import Comm, CommManager

LOGGER = _loggers.marimo_logger()

COMM_MANAGER = MarimoCommManager()

loaded_extension: bool = False
loaded_extensions: list[str] = []

# Weak dictionary
# When the widget is deleted, the UIElement will be deleted as well
cache: dict[Any, UIElement[Any, Any]] = weakref.WeakKeyDictionary()  # type: ignore[no-untyped-call, unused-ignore, assignment]  # noqa: E501


def from_panel(obj: Any) -> UIElement[Any, Any]:
    """Create a UIElement from an Panel."""
    try:
        cached = obj in cache
        cacheable = True
    except TypeError:
        cacheable = cached = False
    if cached:
        ui_element = cache[obj]
    else:
        ui_element = panel(obj)
    if cacheable:
        cache[obj] = ui_element
    return ui_element


T = Dict[str, Any]


@dataclass
class SendToWidgetArgs:
    message: Any
    buffers: Optional[Any] = None


class MarimoPanelComm(Comm):

    def __init__(self, *args: any, **kwargs: any):
        super().__init__(*args, **kwargs)
        self._comm = MarimoComm(
            comm_id=self.id,
            target_name="panel.comms",
            data={},
            comm_manager=COMM_MANAGER,
        )
        self._comm.on_msg(self._handle_msg)
        if self._on_open:
            self._on_open({})

    @classmethod
    def decode(cls, msg: SendToWidgetArgs) -> dict[str, Any]:
        buffers = {i: v for i, v in enumerate(msg.buffers)}
        return dict(msg.message, _buffers=buffers)

    def send(self, data=None, metadata=None, buffers=None) -> None:
        buffers = buffers or []
        self.comm.send({"content": data}, metadata=metadata, buffers=buffers)


def render_extension(load_timeout: int = 500, reloading: bool = False) -> str:
    from bokeh.io.notebook import curstate
    from panel.config import config
    from panel.io.notebook import (
        CDN,
        INLINE,
        Resources,
        _autoload_js,
        _Unset,
        bundle_resources,
        require_components,
        settings,
        state,
    )

    curstate().output_notebook()

    resources = INLINE if config.inline else CDN
    prev_resources = settings.resources(default="server")
    user_resources = settings.resources._user_value is not _Unset
    nb_endpoint = not state._is_pyodide
    resources = Resources.from_bokeh(resources, notebook=nb_endpoint)
    try:
        bundle = bundle_resources(
            None, resources, notebook=nb_endpoint, reloading=reloading,
            enable_mathjax='auto'
        )
        configs, requirements, exports, skip_imports = require_components()
        ipywidget = 'ipywidgets_bokeh' in sys.modules
        bokeh_js = _autoload_js(
            bundle=bundle,
            configs=configs,
            requirements=requirements,
            exports=exports,
            skip_imports=skip_imports,
            ipywidget=ipywidget,
            reloading=reloading,
            load_timeout=load_timeout
        )
    finally:
        if user_resources:
            settings.resources = prev_resources
        else:
            settings.resources.unset_value()
    return bokeh_js


@mddoc
class panel(UIElement[T, T]):
    """
    Create a UIElement from a Panel component.
    This proxies all the widget's attributes and methods.

    **Example.**

    ```python
    import marimo as mo
    import panel as pn

    slider = pn.widgets.IntSlider(start=0, end=10, value=5)
    rx_stars = mo.ui.panel(slider.rx() * '*')

    # In another cell, access its value
    # This works for all widgets
    slider.value
    ```

    **Attributes.**

    - `obj`: The widget being wrapped.

    **Initialization Args.**

    - `obj`: The widget to wrap.
    """

    def __init__(self, obj: Any):
        from bokeh.document import Document
        from bokeh.embed.util import standalone_docs_json_and_render_items
        from panel.config import panel_extension
        from panel.io.model import add_to_doc
        from panel.io.state import state
        from panel.models.comm_manager import CommManager
        from panel.pane import panel

        self.obj = obj = panel(obj)
        # This gets set to True in super().__init__()
        self._initialized = False

        global loaded_extension
        new_exts = [
            ext for ext in panel_extension._loaded_extensions
            if ext not in loaded_extensions
        ]
        if not loaded_extension or new_exts:
            bokeh_js = render_extension(reloading=loaded_extension)
        else:
            bokeh_js = ""
        loaded_extensions.extend(new_exts)
        loaded_extension = True

        doc = Document()
        comm = MarimoPanelComm()
        root = obj._render_model(doc, comm)
        ref = root.ref["id"]
        manager = CommManager(comm_id=comm.id, plot_id=ref)
        obj._comms[ref] = (comm, comm)
        add_to_doc(root, doc, True)
        (docs_json, [render_item]) = standalone_docs_json_and_render_items(
            [root], suppress_callback_warning=True
        )
        render_json = render_item.to_json()

        super().__init__(
            component_name="marimo-panel",
            initial_value=None,
            label="",
            args={
                "extension": bokeh_js,
                "render_json": render_json,
                "docs_json": docs_json
            },
            on_change=None,
            functions=(
                Function(
                    name="send_to_widget",
                    arg_cls=SendToWidgetArgs,
                    function=partial(self._handle_msg, ref, manager),
                ),
            ),
        )

    def _handle_msg(self, ref, manager, msg) -> None:
        comm = self.obj._comms[ref][0]
        msg = comm.decode(msg)
        self.obj._on_msg(ref, manager, msg)
        comm.send(data={'type': 'ACK'})

    def _initialize(
        self,
        initialization_args: InitializationArgs[
            Dict[str, Any], Dict[str, Any]
        ],
    ) -> None:
        super()._initialize(initialization_args)
        for comm, _ in self.obj._comms.values():
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
