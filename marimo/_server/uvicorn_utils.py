# Copyright 2024 Marimo. All rights reserved.
import signal
import sys

import uvicorn
from packaging import version

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def close_uvicorn(server: uvicorn.Server) -> None:
    LOGGER.debug("Shutting down uvicorn")
    # 0.29.0 changed how uvicorn handles signals, making this unnecessary
    # https://github.com/encode/uvicorn/pull/1600
    if version.parse(uvicorn.__version__) < version.parse("0.29.0"):
        server.handle_exit(signal.SIGINT, None)
