# Copyright 2024 Marimo. All rights reserved.
import asyncio
import signal
import sys
from typing import Any

import uvicorn
from packaging import version

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


def initialize_signals() -> None:
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
            ...

        signal.signal(signal.SIGINT, noop)


def close_uvicorn(server: uvicorn.Server) -> None:
    LOGGER.debug("Shutting down uvicorn")

    # Tried using sys.exit(0) to quit instead, but that ends up not being
    # graceful due to the event loop still running
    if (
        version.parse(uvicorn.__version__) >= version.parse("0.29.0")
        # pytest appears to run tests outside the main thread, causing
        # signal functions to fail
        and "pytest" not in sys.modules
    ):
        loop = asyncio.get_running_loop()

        # remove interrupt handler -- uvicorn shouldn't re-interrupt marimo
        # only needed because uvicorn saves original handlers before
        # server.run() is called, then re-raises signals ...
        try:
            loop.remove_signal_handler(signal.SIGINT)
        except NotImplementedError:
            # Windows
            def noop(signum: int, frame: Any) -> None:
                del signum
                del frame
                ...

            signal.signal(signal.SIGINT, noop)

    server.handle_exit(signal.SIGINT, None)

    LOGGER.debug("Shut down uvicorn")
