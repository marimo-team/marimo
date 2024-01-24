# Copyright 2024 Marimo. All rights reserved.
import os
from typing import Optional

import uvicorn

from marimo._config.config import get_configuration
from marimo._server.main import app
from marimo._server.model import SessionMode
from marimo._server.sessions import initialize_manager
from marimo._server.utils import (
    find_free_port,
    import_files,
    initialize_asyncio,
)

DEFAULT_PORT = 2718


def start(
    filename: Optional[str],
    mode: SessionMode,
    development_mode: bool,
    quiet: bool,
    include_code: bool,
    headless: bool,
    port: Optional[int],
) -> None:
    """
    Start the server.
    """

    # Find a free port if none is specified
    # if the user specifies a port, we don't try to find a free one
    port = port or find_free_port(DEFAULT_PORT)

    session_manager = initialize_manager(
        filename=filename,
        mode=mode,
        development_mode=development_mode,
        quiet=quiet,
        include_code=include_code,
        port=port,
    )

    log_level = "info" if development_mode else "error"

    app.state.headless = headless
    app.state.session_manager = session_manager
    app.state.user_config = get_configuration()

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            port=port,
            # TODO: cannot use reload unless the app is an import string
            # although cannot use import string because it breaks the
            # session manager
            # reload=development_mode,
            reload_dirs=[
                os.path.realpath(
                    str(import_files("marimo").joinpath("_static"))
                )
            ]
            if development_mode
            else None,
            log_level=log_level,
            # ping the websocket once a second to prevent intermittent
            # disconnections
            ws_ping_interval=1,
            # close the websocket if we don't receive a pong after 60 seconds
            ws_ping_timeout=60,
            timeout_graceful_shutdown=1,
        )
    )

    app.state.server = server
    initialize_asyncio()
    server.run()
