# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING, Any, TypeVar

from marimo._utils.net import find_free_port as find_free_port

if TYPE_CHECKING:
    from collections.abc import Coroutine


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
