# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import os
import sys
from typing import TYPE_CHECKING, Any, TypeVar

from marimo import _loggers
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from collections.abc import Coroutine

# use spaces instead of a tab to play well with carriage returns;
# \r\t doesn't appear to overwrite characters at the start of a line,
# but \r{TAB} does ...
TAB = "        "

LOGGER = _loggers.marimo_logger()


def print_tabbed(string: str, n_tabs: int = 1) -> None:
    print_(f"{TAB * n_tabs}{string}")


def canonicalize_filename(filename: str) -> str:
    # If its not a valid Python or Markdown file, then add .py
    if not MarimoPath.is_valid_path(filename):
        filename += ".py"
    return os.path.expanduser(filename)


def find_free_port(port: int, attempts: int = 100) -> int:
    """Find a free port or move to the next one recursively"""

    import socket

    # Valid port range is 1-65535
    port = max(1, min(port, 65535))

    if attempts == 0:
        raise RuntimeError("Could not find a free port")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.settimeout(0.1)
            sock.bind(("", port))
            return port
        except OSError:
            LOGGER.debug(f"Port {port} is already in use")
            pass

    # Ensure we don't exceed valid port range
    next_port = min(port + 1, 65535)
    if next_port == port:
        raise RuntimeError("No more ports available")

    return find_free_port(next_port, attempts - 1)


def initialize_mimetypes() -> None:
    import mimetypes

    # Fixes an issue with invalid mimetypes on windows:
    # https://github.com/encode/starlette/issues/829#issuecomment-587163696
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/svg+xml", ".svg")


def initialize_asyncio() -> None:
    """Platform-specific initialization of asyncio.

    Sessions use the `add_reader()` API, which is only available in the
    SelectorEventLoop policy; Windows uses the Proactor by default.
    """
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def initialize_fd_limit(limit: int) -> None:
    """Raise the limit on open file descriptors.

    Not applicable on Windows.
    """
    try:
        import resource
    except ImportError:
        # Windows
        return

    old_soft, old_hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if limit > old_soft and limit <= old_hard:
        resource.setrlimit(resource.RLIMIT_NOFILE, (limit, old_hard))


T = TypeVar("T")


def asyncio_run(coro: Coroutine[Any, Any, T], **kwargs: dict[Any, Any]) -> T:
    """asyncio.run() with platform-specific initialization.

    When using Sessions, make sure to use this method instead of `asyncio.run`.

    If not using a Session, don't call this method.

    `kwargs` are passed to `asyncio.run()`
    """
    initialize_asyncio()
    return asyncio.run(coro, **kwargs)  # type: ignore[arg-type]


def print_(*args: Any, **kwargs: Any) -> None:
    try:
        import click

        click.echo(*args, **kwargs)
    except ImportError:
        print(*args, **kwargs)  # noqa: T201
