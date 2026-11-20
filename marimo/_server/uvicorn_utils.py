# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import signal
from typing import Any

import uvicorn

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def initialize_signals() -> None:
    from packaging import version

    # 0.29.0 changed how uvicorn handles signals
    #
    # https://github.com/encode/uvicorn/pull/1600
    #
    # In 0.29.0, uvicorn re-throws signals after quitting, which leads to
    # ungraceful shutdowns since we use a SIGINT to kill uvicorn in the
    # first place
    #
    # Must be called before a uvicorn server is started
    if version.parse(uvicorn.__version__) >= version.parse("0.29.0"):

        def noop(signum: int, frame: Any) -> None:
            del signum
            del frame

        signal.signal(signal.SIGINT, noop)


def close_uvicorn(server: uvicorn.Server) -> None:
    LOGGER.debug("Shutting down uvicorn")

    # handle_exit records a signal for uvicorn to replay after shutdown.
    # A programmatic shutdown must not synthesize a SIGINT.
    server.should_exit = True

    LOGGER.debug("Shut down uvicorn")
