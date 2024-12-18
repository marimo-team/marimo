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
import os
import signal
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

from marimo import _loggers
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
from marimo._utils.platform import is_pyodide
from marimo._utils.signals import get_signals

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.backends.backend_webagg_core import FigureManagerWebAgg
    from matplotlib.figure import Figure, SubFigure
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.websockets import WebSocket


class FigureManagers:
    def __init__(self) -> None:
        self.figure_managers: dict[str, FigureManagerWebAgg] = {}

    def add(self, manager: FigureManagerWebAgg) -> None:
        self.figure_managers[str(manager.num)] = manager

    def get(self, figure_id: str) -> FigureManagerWebAgg:
        if figure_id not in self.figure_managers:
            raise RuntimeError(f"Figure {figure_id} not found.")  # noqa: E501
        return self.figure_managers[str(figure_id)]

    def remove(self, manager: FigureManagerWebAgg) -> None:
        del self.figure_managers[str(manager.num)]


figure_managers = FigureManagers()


def _get_host() -> str:
    """
    Get the host from environment variable or fall back to localhost.
    """
    host = os.environ.get("MARIMO_MPL_HOST", "localhost")
    if not host or not isinstance(host, str):
        return "localhost"
    if "://" in host:
        raise ValueError(
            f"Invalid host '{host}': should not include protocol (http:// or https://)"
        )
    if "/" in host:
        raise ValueError(f"Invalid host '{host}': should not include paths")
    if ":" in host:
        raise ValueError(
            f"Invalid host '{host}': should not include port numbers"
        )
    return host


def _get_secure() -> bool:
    """
    Get the secure status from environment variable or fall back to False.
    """
    secure = os.environ.get("MARIMO_MPL_SECURE", "false")
    if not secure or not isinstance(secure, str):
        return False
    secure = secure.lower().strip()
    if secure in ("true", "1", "yes", "on"):
        return True
    if secure in ("false", "0", "no", "off"):
        return False

    raise ValueError(
        f"Invalid secure value '{secure}': should be 'true' or 'false'"
    )


def _template(fig_id: str, port: int) -> str:
    return html_content % {
        "ws_uri": f"/mpl/{port}/ws?figure={fig_id}",
        "fig_id": fig_id,
        "port": port,
    }


def create_application() -> Starlette:
    import matplotlib as mpl
    from matplotlib.backends.backend_webagg_core import (
        FigureManagerWebAgg,
    )
    from starlette.applications import Starlette
    from starlette.responses import HTMLResponse, Response
    from starlette.routing import Mount, Route, WebSocketRoute
    from starlette.staticfiles import StaticFiles
    from starlette.websockets import (
        WebSocketDisconnect,
        WebSocketState,
    )

    async def main_page(request: Request) -> HTMLResponse:
        figure_id = request.query_params.get("figure")
        assert figure_id is not None
        port = request.app.state.port
        content = _template(figure_id, port)
        return HTMLResponse(content=content)

    async def mpl_js(request: Request) -> Response:
        del request
        return Response(
            content=FigureManagerWebAgg.get_javascript(),  # type: ignore[no-untyped-call]
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
        queue: asyncio.Queue[Tuple[Any, str]] = asyncio.Queue()

        class SyncWebSocket:
            def send_json(self, content: str) -> None:
                queue.put_nowait((content, "json"))

            def send_binary(self, blob: Any) -> None:
                queue.put_nowait((blob, "binary"))

        figure_id = websocket.query_params.get("figure")
        if not figure_id:
            await websocket.send_json(
                {"type": "error", "message": "No figure ID provided"}
            )
            await websocket.close()
            return

        try:
            figure_manager = figure_managers.get(figure_id)
        except RuntimeError:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Figure with id '{figure_id}' not found",
                }
            )
            await websocket.close()
            return

        figure_manager.add_web_socket(SyncWebSocket())  # type: ignore[no-untyped-call]

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
                        figure_manager.handle_json(data)  # type: ignore[no-untyped-call]
            except WebSocketDisconnect:
                pass
            except Exception as e:
                if websocket.application_state != WebSocketState.DISCONNECTED:
                    await websocket.send_json(
                        {"type": "error", "message": str(e)}
                    )
            finally:
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
            except WebSocketDisconnect:
                # Client disconnected normally
                pass
            except Exception as e:
                if websocket.application_state != WebSocketState.DISCONNECTED:
                    await websocket.send_json(
                        {"type": "error", "message": str(e)}
                    )
            finally:
                if websocket.application_state != WebSocketState.DISCONNECTED:
                    await websocket.close()

        try:
            await asyncio.gather(receive(), send())
        except Exception as e:
            if websocket.application_state != WebSocketState.DISCONNECTED:
                await websocket.send_json({"type": "error", "message": str(e)})
                await websocket.close()

    return Starlette(
        routes=[
            Route("/", main_page, methods=["GET"]),
            Route("/mpl.js", mpl_js, methods=["GET"]),
            Route("/custom.css", mpl_custom_css, methods=["GET"]),
            Route("/download.{fmt}", download, methods=["GET"]),
            WebSocketRoute("/ws", websocket_endpoint),
            Mount(
                "/_static",
                StaticFiles(
                    directory=FigureManagerWebAgg.get_static_file_path()  # type: ignore[no-untyped-call]
                ),
                name="mpl_static",
            ),
            Mount(
                "/_images",
                StaticFiles(directory=Path(mpl.get_data_path(), "images")),
                name="mpl_images",
            ),
        ],
    )


_app: Optional[Starlette] = None


def get_or_create_application(
    app_host: Optional[str] = None,
    free_port: Optional[int] = None,
    secure_host: Optional[bool] = None,
) -> Starlette:
    global _app

    import uvicorn

    if _app is None:
        host = app_host if app_host is not None else _get_host()
        port = free_port if free_port is not None else find_free_port(10_000)
        secure = secure_host if secure_host is not None else _get_secure()
        app = create_application()
        app.state.host = host
        app.state.port = port
        app.state.secure = secure
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


def new_figure_manager_given_figure(
    num: int, figure: Union[Figure, SubFigure, Axes]
) -> Any:
    from matplotlib.backends.backend_webagg_core import (
        FigureCanvasWebAggCore,
        FigureManagerWebAgg as CoreFigureManagerWebAgg,
        NavigationToolbar2WebAgg as CoreNavigationToolbar2WebAgg,
    )

    class FigureManagerWebAgg(CoreFigureManagerWebAgg):
        _toolbar2_class = CoreNavigationToolbar2WebAgg  # type: ignore[assignment]

    class FigureCanvasWebAgg(FigureCanvasWebAggCore):
        manager_class = FigureManagerWebAgg  # type: ignore[assignment]

    canvas = FigureCanvasWebAgg(figure)  # type: ignore[no-untyped-call]
    manager = FigureManagerWebAgg(canvas, num)  # type: ignore[no-untyped-call]
    return manager


@mddoc
def interactive(figure: Union[Figure, SubFigure, Axes]) -> Html:
    """Render a matplotlib figure using an interactive viewer.

    The interactive viewer allows you to pan, zoom, and see plot coordinates
    on mouse hover.

    Example:
        ```python
        plt.plot([1, 2])
        # plt.gcf() gets the current figure
        mo.mpl.interactive(plt.gcf())
        ```

    Args:
        figure (matplotlib Figure or Axes): A matplotlib `Figure` or `Axes` object.

    Returns:
        Html: An interactive matplotlib figure as an `Html` object.
    """
    # We can't support interactive plots in Pyodide
    # since they require a WebSocket connection
    if is_pyodide():
        LOGGER.error(
            "Interactive plots are not supported in Pyodide/WebAssembly"
        )
        return as_html(figure)

    # No top-level imports of matplotlib, since it isn't a required
    # dependency
    from matplotlib.axes import Axes

    if isinstance(figure, Axes):
        maybe_figure = figure.get_figure()
        assert maybe_figure is not None, "Axes object does not have a Figure"
        figure = maybe_figure

    ctx = get_context()
    if not isinstance(ctx, KernelRuntimeContext):
        return as_html(figure)

    # Figure Manager, Any type because matplotlib doesn't have typings
    figure_manager = new_figure_manager_given_figure(id(figure), figure)

    # TODO(akshayka): Proxy this server through the marimo server to help with
    # deployment.
    app = get_or_create_application()
    port = app.state.port

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

    content = _template(str(figure_manager.num), port)

    return Html(
        h.iframe(
            srcdoc=html.escape(content),
            width="100%",
            height="550px",
            onload="__resizeIframe(this)",
        )
    )


html_content = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <base href='/mpl/%(port)s/    ' />
    <link rel="stylesheet" href="/mpl/%(port)s/_static/css/page.css" type="text/css" />
    <link rel="stylesheet" href="/mpl/%(port)s/_static/css/boilerplate.css" type="text/css" />
    <link rel="stylesheet" href="/mpl/%(port)s/_static/css/fbm.css" type="text/css" />
    <link rel="stylesheet" href="/mpl/%(port)s/_static/css/mpl.css" type="text/css" />
    <link rel="stylesheet" href="/mpl/%(port)s/custom.css" type="text/css" />
    <script src="/mpl/%(port)s/mpl.js"></script>

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
