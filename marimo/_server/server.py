# Copyright 2023 Marimo. All rights reserved.
"""The marimo server: serves a marimo app.

A marimo server can be created in edit (read-write) or run (read-only) mode.
When in run mode, an arbitrary number of clients can be connected to the
server, and each client gets their own Python kernel. When in edit mode, at
most one client can be connected.

Each server is tied to a single marimo app; once the server has started, it is
not possible to change the served app.
"""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import webbrowser
from shutil import which
from typing import Any, Optional

import tornado.autoreload
import tornado.ioloop
import tornado.web
import tornado.websocket

from marimo import __version__, _loggers
from marimo._config.config import get_configuration
from marimo._config.utils import load_config
from marimo._server import api, sessions
from marimo._server.model import SessionMode
from marimo._server.print import print_shutdown, print_startup
from marimo._server.server_handler import IOSocketHandler
from marimo._server.server_utils import requires_edit
from marimo._server.utils import (
    TAB,
    import_files,
    initialize_mimetypes,
)

DEFAULT_PORT = 2718
ORIGINAL_SIGINT_HANDLER = signal.getsignal(signal.SIGINT)


def shutdown(with_error: bool = False) -> None:
    """Shutdown the server."""
    mgr = sessions.get_manager()
    if with_error:
        logger = _loggers.marimo_logger()
        logger.fatal("marimo shut down with an error.")
    elif not mgr.quiet:
        print_shutdown()
    mgr.shutdown()
    # TODO(akshayka): This method raises an exception sometimes.
    # debug, or just wrap in a try/except since we're on our way out anyway ...
    tornado.ioloop.IOLoop.current().stop()
    if with_error:
        sys.exit(1)
    else:
        sys.exit(0)


def interrupt_handler(signum: int, frame: Any) -> None:
    del signum
    del frame

    # Restore the original signal handler so re-entering Ctrl+C raises a
    # keyboard interrupt instead of calling this function again (input is not
    # re-entrant, so it's not safe to call this function again)
    signal.signal(signal.SIGINT, ORIGINAL_SIGINT_HANDLER)
    mgr = sessions.get_manager()
    if mgr.quiet:
        shutdown()

    try:
        response = input(
            f"\r{TAB}\033[1;32mAre you sure you want to quit?\033[0m "
            "\033[1m(y/n)\033[0m: "
        )
        if response.lower().strip() == "y":
            shutdown()
    except (KeyboardInterrupt, EOFError):
        print()
        shutdown()

    # Program is still alive: restore the interrupt handler
    signal.signal(signal.SIGINT, interrupt_handler)


class MainHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        mgr = sessions.get_manager()
        # reading the xsrf_token property sets the cookie as a side effect
        self.xsrf_token  # noqa: B018
        title = (
            "marimo"
            if mgr.filename is None
            # filename is used as title, except basename and suffix are
            # stripped and underscores are replaced with spaces
            else os.path.splitext(os.path.basename(mgr.filename))[0].replace(
                "_", " "
            )
        )
        user_config = get_configuration()
        app_config = (
            mgr.app_config.asdict() if mgr.app_config is not None else {}
        )
        self.render(
            "index.html",
            title=title,
            filename=mgr.filename if mgr.filename is not None else "",
            mode="read" if mgr.mode == SessionMode.RUN else "edit",
            version=__version__,
            user_config=json.dumps(user_config),
            app_config=json.dumps(app_config),
            server_token=mgr.server_token,
        )


class ShutdownHandler(tornado.web.RequestHandler):
    """Shutdown the server and all sessions."""

    @requires_edit
    def post(self) -> None:
        shutdown()


class CorsStaticFileHandler(tornado.web.StaticFileHandler):
    def set_default_headers(self) -> None:
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")


def construct_app(
    root: str, development_mode: bool
) -> tornado.web.Application:
    static_dir = os.path.join(root, "assets")
    return tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/iosocket", IOSocketHandler),
            (
                r"/api/kernel/shutdown/",
                ShutdownHandler,
            ),
            (
                r"/api/kernel/instantiate/",
                api.InstantiateHandler,
            ),
            (
                r"/api/kernel/run/",
                api.RunHandler,
            ),
            (
                r"/api/kernel/set_ui_element_value/",
                api.SetUIElementValueHandler,
            ),
            (
                r"/api/kernel/function_call/",
                api.FunctionHandler,
            ),
            (
                r"/api/kernel/set_cell_config/",
                api.SetCellConfigHandler,
            ),
            (
                r"/api/kernel/interrupt/",
                api.InterruptHandler,
            ),
            (
                r"/api/kernel/delete/",
                api.DeleteHandler,
            ),
            (
                r"/api/kernel/code_autocomplete/",
                api.CodeCompleteHandler,
            ),
            (
                r"/api/kernel/directory_autocomplete/",
                api.DirectoryAutocompleteHandler,
            ),
            (
                r"/api/kernel/format/",
                api.FormatHandler,
            ),
            (
                r"/api/kernel/rename/",
                api.RenameHandler,
            ),
            (
                r"/api/kernel/save/",
                api.SaveHandler,
            ),
            (
                r"/api/kernel/save_user_config/",
                api.SaveUserConfigurationHandler,
            ),
            (
                r"/api/kernel/save_app_config/",
                api.SaveAppConfigurationHandler,
            ),
            (
                r"/api/kernel/stdin/",
                api.StdinHandler,
            ),
            (
                r"/api/kernel/read_code/",
                api.ReadCodeHandler,
            ),
            (
                r"/@file/(.*)",
                api.VirtualFileHandler,
            ),
            (
                r"/(favicon\.ico)",
                CorsStaticFileHandler,
                {"path": root},
            ),
            (
                r"/(manifest\.json)",
                CorsStaticFileHandler,
                {"path": root},
            ),
            (
                r"/(android-chrome-(192x192|512x512)\.png)",
                CorsStaticFileHandler,
                {"path": root},
            ),
            (
                r"/assets/(.*)",
                CorsStaticFileHandler,
                {"path": static_dir},
            ),
        ],
        cookie_secret=secrets.token_hex(),
        template_path=root,
        xsrf_cookies=not development_mode,
        debug=development_mode,
        # ping the websocket once a second to prevent intermittent
        # disconnections
        websocket_ping_interval=1,
        # close the websocket if we don't receive a pong after 60 seconds
        websocket_ping_timeout=60,
    )


def connect_app(app: tornado.web.Application, port: Optional[int]) -> int:
    from marimo import _loggers

    logger = _loggers.marimo_logger()
    port_requested_by_user = port is not None
    if port is None:
        port = DEFAULT_PORT

    attempts = 0
    max_attempts = 100 if not port_requested_by_user else 1
    while attempts < max_attempts:
        try:
            app.listen(port)
            break
        except (OSError, socket.error):
            attempts += 1
            logger.debug("Port %d is in use.", port)
            if not port_requested_by_user:
                port += 1

    if attempts >= max_attempts:
        if port_requested_by_user:
            raise OSError(
                48,
                f"Port {port} already in use. Try letting marimo pick a port "
                "for you instead by omitting the port option.",
            )
        raise RuntimeError(
            f"Could not find a free port (tried {max_attempts} ports)."
        )
    return port


async def start_server(
    port: Optional[int] = None,
    headless: bool = False,
    filename: Optional[str] = None,
    run: bool = False,
    development_mode: bool = False,
    quiet: bool = False,
    include_code: bool = False,
) -> None:
    """Start the server.

    Args:
    ----
    port: port on which to listen
    headless: if False, opens a client connection in user's browser
    filename: path to marimo app to serve; if None, opens a blank app
    run: if True, starts the server in run (read-only) mode; if False, runs
        in edit (read-write) mode.
    development_mode: if True, enables tornado debug logging and autoreloading
    include_code: if True, return the code to the frontend when in run mode
    """

    initialize_mimetypes()

    logger = _loggers.marimo_logger()
    _loggers.initialize_tornado_loggers(development_mode)
    signal.signal(signal.SIGINT, interrupt_handler)

    root = os.path.realpath(str(import_files("marimo").joinpath("_static")))
    app = construct_app(root=root, development_mode=development_mode)
    port = connect_app(app, port)
    session_mgr = sessions.initialize_manager(
        filename=filename,
        mode=(SessionMode.EDIT if not run else SessionMode.RUN),
        port=port,
        development_mode=development_mode,
        quiet=quiet,
        include_code=include_code,
    )

    try:
        load_config()
    except Exception as e:
        logger.fatal("Error parsing the marimo configuration file: ")
        logger.fatal(type(e).__name__ + ": " + str(e))
        shutdown(with_error=True)

    user_config = get_configuration()
    if not run and user_config["completion"]["copilot"]:
        logger.debug("GitHub Copilot is enabled")
        session_mgr.start_lsp_server()

    url = f"http://localhost:{port}"
    if not headless:
        browser = user_config["server"]["browser"]
        if which("xdg-open") is not None and browser == "default":
            with open(os.devnull, "w") as devnull:
                if sys.platform == "win32" or sys.platform == "cygwin":
                    preexec_fn = None
                else:
                    preexec_fn = os.setpgrp
                subprocess.Popen(
                    ["xdg-open", url],
                    # don't forward signals: ctrl-c shouldn't kill the browser
                    # TODO: test/workaround on windows
                    preexec_fn=preexec_fn,
                    stdout=devnull,
                    stderr=subprocess.STDOUT,
                )
        else:
            controller = (
                webbrowser if browser == "default" else webbrowser.get(browser)
            )
            # type ignore: getting an invalid type error
            controller.open(url)  # type:ignore[attr-defined]

    if not session_mgr.quiet:
        print_startup(filename, url, run)

    if development_mode:
        tornado.autoreload.start()
        for dirname, _, files in os.walk(str(root)):
            for f in files:
                if f.startswith("."):
                    continue
                tornado.autoreload.watch(os.path.join(dirname, f))

        tornado.autoreload.add_reload_hook(session_mgr.close_all_sessions)
    shutdown_event = asyncio.Event()
    await shutdown_event.wait()


if __name__ == "__main__":
    asyncio.run(start_server(port=DEFAULT_PORT, development_mode=True))
