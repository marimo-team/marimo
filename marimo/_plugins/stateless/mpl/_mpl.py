# Copyright 2024 Marimo. All rights reserved.
"""
Interactive matplotlib plots, based on WebAgg.

Adapted from https://matplotlib.org/stable/gallery/user_interfaces/embedding_webagg_sgskip.html
"""

from __future__ import annotations

import asyncio
import html
import io
import mimetypes
import signal
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Tuple

from marimo._output.builder import h
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._runtime.context import (
    RuntimeContext,
    get_context,
)
from marimo._runtime.context.kernel_context import KernelRuntimeContext
from marimo._server.utils import find_free_port
from marimo._utils.signals import get_signals

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.websockets import WebSocket


class FigureManagers:
    def __init__(self) -> None:
        self.figure_managers: dict[str, Any] = {}

    def add(self, manager: Any) -> None:
        self.figure_managers[str(manager.num)] = manager

    def get(self, figure_id: str) -> Any:
        if figure_id not in self.figure_managers:
            raise RuntimeError(f"Figure {figure_id} not found.")  # noqa: E501
        return self.figure_managers[str(figure_id)]

    def remove(self, manager: Any) -> None:
        del self.figure_managers[str(manager.num)]


figure_managers = FigureManagers()


def _template(
    host: str,
    port: int,
    fig_id: str,
) -> str:
    return html_content % {
        "ws_uri": f"ws://{host}:{port}/ws?figure={fig_id}",
        "fig_id": fig_id,
        "base_url": f"http://{host}:{port}",
    }


def create_application(
    host: str,
    port: int,
) -> Starlette:
    import matplotlib as mpl  # type: ignore
    from matplotlib.backends.backend_webagg import (  # type: ignore
        FigureManagerWebAgg,
    )
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, Response
    from starlette.routing import Mount, Route, WebSocketRoute
    from starlette.staticfiles import StaticFiles

    async def main_page(request: Request) -> HTMLResponse:
        figure_id = request.query_params.get("figure")
        assert figure_id is not None
        content = _template(host, port, figure_id)
        return HTMLResponse(content=content)

    async def mpl_js(request: Request) -> Response:
        del request
        return Response(
            content=FigureManagerWebAgg.get_javascript(),  # type: ignore
            media_type="application/javascript",
        )

    async def mpl_custom_css(request: Request) -> Response:
        del request
        return Response(
            content=css_content,
            media_type="text/css",
        )

    async def download(request: Request) -> Response:
        figure_id = request.query_params.get("figure")
        assert figure_id is not None
        fmt = request.path_params["fmt"]
        mime_type = mimetypes.types_map.get(fmt, "binary")
        buff = io.BytesIO()
        figure_manager = figure_managers.get(figure_id)
        figure_manager.canvas.figure.savefig(
            buff, format=fmt, bbox_inches="tight"
        )
        return Response(content=buff.getvalue(), media_type=mime_type)

    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        queue = asyncio.Queue[Tuple[Any, str]]()

        class SyncWebSocket:
            def send_json(self, content: str) -> None:
                queue.put_nowait((content, "json"))

            def send_binary(self, blob: Any) -> None:
                queue.put_nowait((blob, "binary"))

        figure_id = websocket.query_params.get("figure")
        assert figure_id is not None
        figure_manager = figure_managers.get(figure_id)
        figure_manager.add_web_socket(SyncWebSocket())

        async def receive() -> None:
            try:
                while True:
                    data = await websocket.receive_json()
                    if data["type"] == "supports_binary":
                        # We always support binary
                        # and we don't need to pass this message
                        # to the figure manager
                        pass
                    else:
                        figure_manager.handle_json(data)
            except Exception:
                pass
            finally:
                from starlette.websockets import WebSocketState

                if websocket.application_state != WebSocketState.DISCONNECTED:
                    await websocket.close()

        async def send() -> None:
            try:
                while True:
                    (data, mode) = await queue.get()
                    if mode == "json":
                        await websocket.send_json(data)
                    else:
                        await websocket.send_bytes(data)
            except Exception:
                pass
            finally:
                from starlette.websockets import WebSocketState

                if websocket.application_state != WebSocketState.DISCONNECTED:
                    await websocket.close()

        await asyncio.gather(receive(), send())

    return Starlette(
        routes=[
            Route("/", main_page, methods=["GET"]),
            Route("/mpl/mpl.js", mpl_js, methods=["GET"]),
            Route("/mpl/custom.css", mpl_custom_css, methods=["GET"]),
            Route("/download.{fmt}", download, methods=["GET"]),
            WebSocketRoute("/ws", websocket_endpoint),
            Mount(
                "/mpl/_static",
                StaticFiles(
                    directory=FigureManagerWebAgg.get_static_file_path()  # type: ignore # noqa: E501
                ),
                name="mpl_static",
            ),
            Mount(
                "/_images",
                StaticFiles(directory=Path(mpl.get_data_path(), "images")),
                name="images",
            ),
        ],
    )


_app: Optional[Starlette] = None


def get_or_create_application() -> Starlette:
    global _app

    import uvicorn

    if _app is None:
        host = "localhost"
        port = find_free_port(10_000)
        app = create_application(host, port)
        app.state.host = host
        app.state.port = port
        _app = app

        def start_server() -> None:
            signal_handlers = get_signals()
            uvicorn.Server(
                uvicorn.Config(
                    app=app,
                    port=port,
                    host=host,
                    log_level="critical",
                )
            ).run()
            for signo, handler in signal_handlers.items():
                signal.signal(signo, handler)

        threading.Thread(target=start_server).start()

        # arbitrary wait 200ms for the server to start
        # this only happens once per session
        time.sleep(0.02)

    return _app


@mddoc
def interactive(figure: "Figure | Axes") -> Html:  # type: ignore[name-defined] # noqa:F821,E501
    """Render a matplotlib figure using an interactive viewer.

    The interactive viewer allows you to pan, zoom, and see plot coordinates
    on mouse hover.

    **Example**:

    ```python
    plt.plot([1, 2])
    # plt.gcf() gets the current figure
    mo.mpl.interactive(plt.gcf())
    ```

    **Args**:

    - figure: a matplotlib `Figure` or `Axes` object

    **Returns**:

    - An interactive matplotlib figure as an `Html` object
    """
    # No top-level imports of matplotlib, since it isn't a required
    # dependency
    from matplotlib.axes import (  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
        Axes,
    )
    from matplotlib.backends.backend_webagg import (  # type: ignore
        new_figure_manager_given_figure,
    )

    if isinstance(figure, Axes):
        figure = figure.get_figure()

    ctx = get_context()
    if not isinstance(ctx, KernelRuntimeContext):
        return as_html(figure)

    # Figure Manager, Any type because matplotlib doesn't have typings
    figure_manager = new_figure_manager_given_figure(id(figure), figure)

    # TODO(akshayka): Proxy this server through the marimo server to help with
    # deployment.
    application = get_or_create_application()
    host = application.state.host
    port = application.state.port

    class CleanupHandle(CellLifecycleItem):
        def create(self, context: RuntimeContext) -> None:
            del context

        def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
            del context
            del deletion
            figure_managers.remove(figure_manager)
            return True

    figure_managers.add(figure_manager)
    assert ctx.execution_context is not None
    ctx.cell_lifecycle_registry.add(CleanupHandle())
    ctx.stream.cell_id = ctx.execution_context.cell_id

    content = _template(host, port, str(figure_manager.num))

    return Html(
        h.iframe(
            # srcdoc allows us to use __resizeIframe
            srcdoc=html.escape(content),
            width="100%",
            height="550px",
            onload="__resizeIframe(this)",
        )
    )


html_content = """
<!DOCTYPE html>
<html lang="en">
  <base href="%(base_url)s" />
  <head>
    <link rel="stylesheet" href="mpl/_static/css/page.css" type="text/css" />
    <link rel="stylesheet" href="mpl/_static/css/boilerplate.css" type="text/css" />
    <link rel="stylesheet" href="mpl/_static/css/fbm.css" type="text/css" />
    <link rel="stylesheet" href="mpl/_static/css/mpl.css" type="text/css" />
    <link rel="stylesheet" href="mpl/custom.css" type="text/css" />
    <script src="mpl/mpl.js"></script>

    <script>
      function ondownload(figure, format) {
        window.open('download.' + format + '?figure=' + figure.id, '_blank');
      };

      function ready(fn) {
        if (document.readyState != "loading") {
          fn();
        } else {
          document.addEventListener("DOMContentLoaded", fn);
        }
      }

      ready(
        function() {
          var websocket_type = mpl.get_websocket_type();
          var websocket = new websocket_type("%(ws_uri)s");

          // mpl.figure creates a new figure on the webpage.
          var fig = new mpl.figure(
              // A unique numeric identifier for the figure
              %(fig_id)s,
              // A websocket object
              websocket,
              // A function called when a file type is selected for download
              ondownload,
              // The HTML element in which to place the figure
              document.getElementById("figure"));
        }
      );
    </script>

    <title>marimo</title>
  </head>

  <body>
    <div id="figure"></div>
  </body>
</html>
""".strip()  # noqa: E501

# Custom CSS to make the mpl toolbar fit the marimo UI
# We do not support dark mode at the moment as the iframe does not know
# the theme of the parent page.
css_content = """
body {
    background-color: transparent;
    width: 100%;
}
#figure, mlp-canvas {
    width: 100%;
}
.ui-dialog-titlebar + div {
    border-radius: 4px;
}
.ui-dialog-titlebar {
    display: none;
}
.mpl-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
}
select.mpl-widget,
.mpl-button-group {
    margin: 4px 0;
    border-radius: 6px;
    box-shadow: rgba(0, 0, 0, 0) 0px 0px 0px 0px,
        rgba(0, 0, 0, 0) 0px 0px 0px 0px,
        rgba(15, 23, 42, 0.1) 1px 1px 0px 0px,
        rgba(15, 23, 42, 0.1) 0px 0px 2px 0px;
}
.mpl-button-group + .mpl-button-group {
    margin-left: 0;
}
.mpl-button-group > .mpl-widget {
    padding: 4px;
}
.mpl-button-group > .mpl-widget > img {
    height: 16px;
    width: 16px;
}
.mpl-widget:disabled, .mpl-widget[disabled]
.mpl-widget:disabled, .mpl-widget[disabled]:hover {
    opacity: 0.5;
    background-color: #fff;
    border-color: #ccc !important;
}
.mpl-message {
    color: rgb(139, 141, 152);
    font-size: 11px;
}
.mpl-widget img {
    filter: invert(0.3);
}
""".strip()
