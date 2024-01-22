# Copyright 2023 Marimo. All rights reserved.
"""
Interactive matplotlib plots, based on WebAgg.

Adapted from https://matplotlib.org/stable/gallery/user_interfaces/embedding_webagg_sgskip.html
"""

from __future__ import annotations

import asyncio
import io
import mimetypes
import threading
from pathlib import Path
from typing import Any, Optional, Tuple

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._runtime.cell_lifecycle_item import CellLifecycleItem
from marimo._runtime.context import (
    ContextNotInitializedError,
    RuntimeContext,
    get_context,
)
from marimo._server.utils import find_free_port


def create_application(
    figure: Any,
    host: str,
    port: int,
) -> Starlette:
    import matplotlib as mpl  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501
    from matplotlib.backends.backend_webagg import (
        FigureManagerWebAgg,
        new_figure_manager_given_figure,
    )

    # Figure Manager, Any type because matplotlib doesn't have typings
    manager: Any = new_figure_manager_given_figure(id(figure), figure)

    async def main_page(request: Request):
        ws_uri = f"ws://{host}:{port}/ws"

        content = html_content % {
            "ws_uri": ws_uri,
            "fig_id": manager.num,
            "custom_css": css_content,
        }
        # return HTMLResponse(content="Hello World")
        return HTMLResponse(content=content)

    async def mpl_js(request: Request):
        return Response(
            content=FigureManagerWebAgg.get_javascript(),
            media_type="application/javascript",
        )

    async def download(request: Request):
        fmt = request.path_params["fmt"]
        mime_type = mimetypes.types_map.get(fmt, "binary")
        buff = io.BytesIO()
        manager.canvas.figure.savefig(buff, format=fmt)
        return Response(content=buff.getvalue(), media_type=mime_type)

    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()

        queue = asyncio.Queue[Tuple[Any, str]]()

        class SyncWebSocket:
            def send_json(self, content: str) -> None:
                queue.put_nowait((content, "json"))

            def send_binary(self, blob: Any) -> None:
                queue.put_nowait((blob, "binary"))

        manager.add_web_socket(SyncWebSocket())

        async def receive() -> None:
            try:
                while True:
                    data = await websocket.receive_json()
                    manager.handle_json(data)
            except Exception:
                pass
            finally:
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
                await websocket.close()

        await asyncio.gather(receive(), send())

    return Starlette(
        routes=[
            Route("/", main_page, methods=["GET"]),
            Route("/mpl/mpl.js", mpl_js, methods=["GET"]),
            Route("/download.{fmt}", download, methods=["GET"]),
            WebSocketRoute("/ws", websocket_endpoint),
            Mount(
                "/mpl/_static",
                StaticFiles(
                    directory=FigureManagerWebAgg.get_static_file_path()
                ),
                name="mpl_static",
            ),
            Mount(
                "/_images",
                StaticFiles(directory=Path(mpl.get_data_path(), "images")),
                name="images",
            ),
        ]
    )


class CleanupHandle(CellLifecycleItem):
    """Handle to shutdown a figure server."""

    shutdown_event: Optional[asyncio.Event] = None

    def create(self, context: RuntimeContext) -> None:
        del context
        pass

    def dispose(self, context: RuntimeContext, deletion: bool) -> bool:
        del context
        del deletion
        if self.shutdown_event is not None:
            self.shutdown_event.set()
        # TODO: if Html containing server is cached, disposal still trashes
        # it, which is a bug ... fix this. Use `deletion` flag to make
        # sure shutdown happens on cell deletion, otherwise need to
        # find a way to keep server alive if its Html is cached.
        return True


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

    if isinstance(figure, Axes):
        figure = figure.get_figure()

    try:
        ctx = get_context()
    except ContextNotInitializedError as err:
        raise RuntimeError(
            "marimo.mpl.interactive can't be used when running as a script."
        ) from err

    host = "localhost"
    port = find_free_port(10_000)

    # TODO(akshayka): Proxy this server through the marimo server to help with
    # deployment.
    application = create_application(figure, host, port)
    cleanup_handle = CleanupHandle()

    def start_server() -> None:
        uvicorn.Server(
            uvicorn.Config(
                app=application,
                port=port,
                host=host,
            )
        ).run()

    assert ctx.kernel.execution_context is not None
    ctx.cell_lifecycle_registry.add(cleanup_handle)
    threading.Thread(target=start_server).start()
    return Html(
        h.iframe(
            src=f"http://{host}:{port}/",
            width="100%",
            height="550px",
        )
    )


html_content = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <link rel="stylesheet" href="mpl/_static/css/page.css" type="text/css" />
    <link rel="stylesheet" href="mpl/_static/css/boilerplate.css" type="text/css" />
    <link rel="stylesheet" href="mpl/_static/css/fbm.css" type="text/css" />
    <link rel="stylesheet" href="mpl/_static/css/mpl.css" type="text/css" />
    <script src="mpl/mpl.js"></script>
    <style>
    %(custom_css)s
    </style>

    <script>
      function ondownload(figure, format) {
        window.open('download.' + format, '_blank');
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
    height: 400px;
    width: 100%;
}
#figure, mlp-canvas {
    height: 400px;
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
