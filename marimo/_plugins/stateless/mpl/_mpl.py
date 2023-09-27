# Copyright 2023 Marimo. All rights reserved.
"""
Interactive matplotlib plots, based on WebAgg.

Adapted from https://matplotlib.org/stable/gallery/user_interfaces/embedding_webagg_sgskip.html
"""

from __future__ import annotations

import asyncio
import io
import json
import mimetypes
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.netutil
import tornado.web
import tornado.websocket

from marimo._ast.cell import CellId_t
from marimo._output.builder import h
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._runtime.context import get_context

# The following is the content of the web page.  You would normally
# generate this using some sort of template facility in your web
# framework, but here we just use Python string formatting.
html_content = """<!DOCTYPE html>
<html lang="en">
  <head>
    <!-- TODO: There should be a way to include all of the required javascript
               and CSS so matplotlib can add to the set in the future if it
               needs to. -->
    <link rel="stylesheet" href="_static/css/page.css" type="text/css">
    <link rel="stylesheet" href="_static/css/boilerplate.css" type="text/css">
    <link rel="stylesheet" href="_static/css/fbm.css" type="text/css">
    <link rel="stylesheet" href="_static/css/mpl.css" type="text/css">
    <script src="mpl.js"></script>

    <script>
      /* This is a callback that is called when the user saves
         (downloads) a file.  Its purpose is really to map from a
         figure and file format to a url in the application. */
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
          /* It is up to the application to provide a websocket that the figure
             will use to communicate to the server.  This websocket object can
             also be a "fake" websocket that underneath multiplexes messages
             from multiple figures, if necessary. */
          var websocket_type = mpl.get_websocket_type();
          var websocket = new websocket_type("%(ws_uri)sws");

          // mpl.figure creates a new figure on the webpage.
          var fig = new mpl.figure(
              // A unique numeric identifier for the figure
              %(fig_id)s,
              // A websocket object (or something that behaves like one)
              websocket,
              // A function called when a file type is selected for download
              ondownload,
              // The HTML element in which to place the figure
              document.getElementById("figure"));
        }
      );
    </script>

    <title>matplotlib</title>
  </head>

  <body>
    <div id="figure">
    </div>
  </body>
</html>
"""


class MyApplication(tornado.web.Application):
    class MainPage(tornado.web.RequestHandler):
        """
        Serves the main HTML page.
        """

        def get(self) -> None:
            manager = self.application.manager  # type: ignore[attr-defined]
            ws_uri = f"ws://{self.request.host}/"
            content = html_content % {"ws_uri": ws_uri, "fig_id": manager.num}
            self.write(content)

    class MplJs(tornado.web.RequestHandler):
        """
        Serves the generated matplotlib javascript file.  The content
        is dynamically generated based on which toolbar functions the
        user has defined.  Call `FigureManagerWebAgg` to get its
        content.
        """

        def get(self) -> None:
            from matplotlib.backends.backend_webagg import (  # type: ignore
                FigureManagerWebAgg,
            )

            self.set_header("Content-Type", "application/javascript")
            js_content = FigureManagerWebAgg.get_javascript()

            self.write(js_content)

    class Download(tornado.web.RequestHandler):
        """
        Handles downloading of the figure in various file formats.
        """

        def get(self, fmt: str) -> None:
            manager = self.application.manager  # type: ignore[attr-defined]
            self.set_header(
                "Content-Type", mimetypes.types_map.get(fmt, "binary")
            )
            buff = io.BytesIO()
            manager.canvas.figure.savefig(buff, format=fmt)
            self.write(buff.getvalue())

    class WebSocket(tornado.websocket.WebSocketHandler):
        """
        A websocket for interactive communication between the plot in
        the browser and the server.

        In addition to the methods required by tornado, it is required to
        have two callback methods:

            - ``send_json(json_content)`` is called by matplotlib when
              it needs to send json to the browser.  `json_content` is
              a JSON tree (Python dictionary), and it is the responsibility
              of this implementation to encode it as a string to send over
              the socket.

            - ``send_binary(blob)`` is called to send binary image data
              to the browser.
        """

        supports_binary = True

        def open(self, *args: str, **kwargs: str) -> None:
            del args
            del kwargs
            # Register the websocket with the FigureManager.
            manager = self.application.manager  # type: ignore[attr-defined]
            manager.add_web_socket(self)
            if hasattr(self, "set_nodelay"):
                self.set_nodelay(True)

        def on_close(self) -> None:
            # When the socket is closed, deregister the websocket with
            # the FigureManager.
            manager = self.application.manager  # type: ignore[attr-defined]
            manager.remove_web_socket(self)

        def on_message(self, message: Any) -> None:
            # The 'supports_binary' message is relevant to the
            # websocket itself.  The other messages get passed along
            # to matplotlib as-is.

            # Every message has a "type" and a "figure_id".
            message = json.loads(message)
            if message["type"] == "supports_binary":
                self.supports_binary = message["value"]
            else:
                manager = self.application.manager  # type: ignore[attr-defined] # noqa: E501
                manager.handle_json(message)

        def send_json(self, content: str) -> None:
            self.write_message(json.dumps(content))

        def send_binary(self, blob: Any) -> None:
            if self.supports_binary:
                self.write_message(blob, binary=True)
            else:
                data_uri = "data:image/png;base64," + blob.encode(
                    "base64"
                ).replace("\n", "")
                self.write_message(data_uri)

    def __init__(self, figure: Any) -> None:
        import matplotlib as mpl  # type: ignore[import]
        from matplotlib.backends.backend_webagg import (
            FigureManagerWebAgg,
            new_figure_manager_given_figure,
        )

        self.figure = figure
        self.manager = new_figure_manager_given_figure(id(figure), figure)

        super().__init__(
            [
                # Static files for the CSS and JS
                (
                    r"/_static/(.*)",
                    tornado.web.StaticFileHandler,
                    {"path": FigureManagerWebAgg.get_static_file_path()},
                ),
                # Static images for the toolbar
                (
                    r"/_images/(.*)",
                    tornado.web.StaticFileHandler,
                    {"path": Path(mpl.get_data_path(), "images")},
                ),
                # The page that contains all of the pieces
                ("/", self.MainPage),
                ("/mpl.js", self.MplJs),
                # Sends images and events to the browser, and receives
                # events from the browser
                ("/ws", self.WebSocket),
                # Handles the downloading (i.e., saving) of static images
                (r"/download.([a-z0-9.]+)", self.Download),
            ]
        )


@dataclass
class CleanupHandle:
    """Handle to shutdown a figure server."""

    shutdown_event: Optional[asyncio.Event] = None


class InteractiveMplRegistry:
    """Registry of figures created by each cell.

    Allows the kernel to tear down all figures for a given cell.
    """

    _registry: dict[CellId_t, list[CleanupHandle]] = {}

    def register(
        self, cell_id: CellId_t, cleanup_handle: CleanupHandle
    ) -> None:
        """Register a figure's cleanup handle for a cell."""
        if cell_id not in self._registry:
            self._registry[cell_id] = [cleanup_handle]
        else:
            self._registry[cell_id].append(cleanup_handle)

    def cleanup(self, cell_id: CellId_t) -> None:
        """Tear down figures for a cell."""
        if cell_id in self._registry:
            for cleanup_handle in self._registry[cell_id]:
                if cleanup_handle.shutdown_event is not None:
                    cleanup_handle.shutdown_event.set()
            del self._registry[cell_id]


@mddoc
def interactive(figure: "Figure | Axes") -> Html:  # type: ignore[name-defined] # noqa:F821,E501
    """Render a matplotlib figure using an interactive viewer.

    The interactive viewer allows you to pan and zoom, and see plot coordinates
    on mouse hover.

    **Example**:

    ```python
    fig = plt.figure()
    plt.plot([1, 2])
    mo.mpl.interactive(fig)
    ```

    **Args**:

    - figure: a matplotlib Figure or Axes object

    **Returns**:

    - An interactive matplotlib figure as an `Html` object
    """
    # No top-level imports of matplotlib, since it isn't a required
    # dependency
    from matplotlib.axes import Axes  # type: ignore[import]

    if isinstance(figure, Axes):
        figure = figure.get_figure()

    ctx = get_context()
    if not ctx.initialized:
        raise RuntimeError(
            "marimo.mpl.interactive can't be used when running as a script."
        )

    application = MyApplication(figure)
    cleanup_handle = CleanupHandle()
    sockets = tornado.netutil.bind_sockets(0, "")

    async def main() -> None:
        # create the shutdown event in the coroutine for py3.8, 3.9 compat
        cleanup_handle.shutdown_event = asyncio.Event()
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.add_sockets(sockets)
        await cleanup_handle.shutdown_event.wait()

    def start_server() -> None:
        asyncio.run(main())

    addr: Optional[str] = None
    port: Optional[int] = None
    for s in sockets:
        addr, port = s.getsockname()[:2]
        if s.family is socket.AF_INET6:
            addr = f"[{addr}]"
        print(f"Listening on http://{addr}:{port}/")
    if addr is None or port is None:
        raise RuntimeError("Failed to create sockets for mpl interactive.")

    assert ctx.kernel.execution_context is not None
    ctx.interactive_mpl_registry.register(
        cell_id=ctx.kernel.execution_context.cell_id,
        cleanup_handle=cleanup_handle,
    )

    threading.Thread(target=start_server).start()
    return Html(
        h.iframe(
            src=f"http://{addr}:{port}/",
            width="100%",
            height="550px",
        )
    )
