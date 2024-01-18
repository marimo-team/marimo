import os
from typing import Optional

import uvicorn

from marimo._server.sessions import SessionMode, initialize_manager
from marimo._server.utils import find_free_port, import_files
from marimo._server2.main import app

DEFAULT_PORT = 2718


def start(
    filename: Optional[str],
    mode: SessionMode,
    development_mode: bool,
    quiet: bool,
    include_code: bool,
    headless: bool,
    port: Optional[int],
):
    """
    Start the server.
    """

    # Find a free port if none is specified
    # if the user specifies a port, we don't try to find a free one
    port = port or find_free_port(DEFAULT_PORT)

    initialize_manager(
        filename=filename,
        mode=mode,
        development_mode=development_mode,
        quiet=quiet,
        include_code=include_code,
        port=port,
    )

    log_level = "info" if development_mode else "error"

    app.state.headless = headless

    uvicorn.run(
        app,
        port=port,
        # TODO: cannot use reload unless the app is an import string
        # although cannot use import string because it breaks the
        # session manager
        # reload=development_mode,
        reload_dirs=[
            os.path.realpath(str(import_files("marimo").joinpath("_static")))
        ],
        log_level=log_level,
        # ping the websocket once a second to prevent intermittent
        # disconnections
        ws_ping_interval=1,
        # close the websocket if we don't receive a pong after 60 seconds
        ws_ping_timeout=60,
    )
