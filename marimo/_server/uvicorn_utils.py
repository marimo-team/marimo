# Copyright 2024 Marimo. All rights reserved.
import signal

import uvicorn

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def close_uvicorn(server: uvicorn.Server) -> None:
    LOGGER.debug("Shutting down uvicorn")
    server.handle_exit(signal.SIGINT, None)
    LOGGER.debug("Uvicorn shut down")
