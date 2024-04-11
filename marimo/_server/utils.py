# Copyright 2024 Marimo. All rights reserved.
import asyncio
import os
import pathlib
import sys

from marimo import _loggers

# use spaces instead of a tab to play well with carriage returns;
# \r\t doesn't appear to overwrite characters at the start of a line,
# but \r{TAB} does ...
TAB = "        "

LOGGER = _loggers.marimo_logger()


def print_tabbed(string: str, n_tabs: int = 1) -> None:
    print(f"{TAB * n_tabs}{string}")


def canonicalize_filename(filename: str) -> str:
    if pathlib.Path(filename).suffix != ".py":
        filename += ".py"
    return os.path.expanduser(filename)


def find_free_port(port: int, attempts: int = 100) -> int:
    """Find a free port or move to the next one recursively"""

    import socket

    if attempts == 0:
        raise RuntimeError("Could not find a free port")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            in_use = sock.connect_ex(("localhost", port)) == 0
            if not in_use:
                return port
        except OSError:
            LOGGER.debug(f"Port {port} is already in use")
            pass
    return find_free_port(port + 1, attempts - 1)


def initialize_mimetypes() -> None:
    import mimetypes

    # Fixes an issue with invalid mimetypes on windows:
    # https://github.com/encode/starlette/issues/829#issuecomment-587163696
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/svg+xml", ".svg")


def initialize_asyncio() -> None:
    """Platform-specific initialization of asyncio."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
