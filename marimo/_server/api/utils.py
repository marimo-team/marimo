# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, Optional, TypeVar

from marimo._runtime.requests import ControlRequest
from marimo._server.models.models import SuccessResponse
from marimo._types.ids import ConsumerId
from marimo._utils.parse_dataclass import parse_raw

if TYPE_CHECKING:
    from starlette.requests import Request


async def parse_request(
    request: Request, cls: type[T], allow_unknown_keys: bool = False
) -> T:
    """Parse the request body as a dataclass of type `cls`"""
    return parse_raw(
        await request.body(), cls=cls, allow_unknown_keys=allow_unknown_keys
    )


async def dispatch_control_request(
    request: Request,
    cls: type[ControlRequest] | ControlRequest,
) -> SuccessResponse:
    """
    Parse a request and dispatch it to the current session.
    """
    from marimo._server.api.deps import AppState

    app_state = AppState(request)
    if isinstance(cls, type):
        body = await parse_request(request, cls)
    else:
        body = cls
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()


def parse_title(filepath: Optional[str]) -> str:
    """
    Create a title from a filename.
    """
    if filepath is None:
        return "marimo"

    # filename is used as title, except basename and suffix are
    # stripped and underscores are replaced with spaces
    return Path(filepath).stem.replace("_", " ")


def open_url_in_browser(browser: str, url: str) -> None:
    """
    Open a browser to the given URL.
    """
    if which("xdg-open") is not None and browser == "default":
        if (
            sys.platform == "win32"
            or sys.platform == "cygwin"
            or sys.implementation.name == "graalpy"
        ):
            preexec_fn = None
        else:
            preexec_fn = os.setpgrp
        subprocess.Popen(
            ["xdg-open", url],
            # don't forward signals: ctrl-c shouldn't kill the browser
            # TODO: test/workaround on windows
            preexec_fn=preexec_fn,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    else:
        if browser == "default":
            webbrowser.open(url)
        else:
            webbrowser.get(browser).open(url)


T = TypeVar("T")
