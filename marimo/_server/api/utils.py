# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Protocol,
    TypeVar,
    runtime_checkable,
)

import msgspec

from marimo._runtime.commands import CommandMessage
from marimo._server.models.models import SuccessResponse
from marimo._types.ids import ConsumerId
from marimo._utils.parse_dataclass import parse_raw

if TYPE_CHECKING:
    from starlette.requests import Request

    from marimo._session.session import Session


async def parse_request(
    request: Request, cls: type[T], allow_unknown_keys: bool = False
) -> T:
    """Parse the request body as a dataclass of type `cls`"""
    return parse_raw(
        await request.body(), cls=cls, allow_unknown_keys=allow_unknown_keys
    )


S = TypeVar("S", bound=msgspec.Struct)


@dataclass
class MultipartRequest(Generic[S]):
    """Result of parsing a multipart/form-data request body."""

    body: S
    files: dict[str, bytes]


async def parse_multipart_request(
    request: Request, cls: type[S]
) -> MultipartRequest[S]:
    """Parse a multipart/form-data body into a msgspec.Struct + file bytes.

    String form fields are validated against `cls`. File upload parts are
    read fully into memory and returned in `files`, keyed by form-field
    name (callers look them up explicitly rather than via the struct).

    Raises msgspec.ValidationError if required string fields are missing
    or invalid.
    """
    # Imported lazily so this module stays import-safe in environments
    # without starlette (e.g. pyodide).
    from starlette.datastructures import UploadFile

    # Use as an async context manager so any spooled temp files backing
    # UploadFile parts are closed after parsing.
    async with request.form() as form:
        string_payload: dict[str, Any] = {}
        files: dict[str, bytes] = {}
        for key, value in form.multi_items():
            if isinstance(value, UploadFile):
                files[key] = await value.read()
            elif isinstance(value, str):
                string_payload[key] = value
    body = msgspec.convert(string_payload, cls, strict=False)
    return MultipartRequest(body=body, files=files)


@runtime_checkable
class RequestAsCommand(Protocol):
    """Protocol for requests that can be converted to commands."""

    def as_command(self) -> CommandMessage: ...


async def dispatch_control_request(
    request: Request,
    cls: type[CommandMessage] | CommandMessage,
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
    if isinstance(body, RequestAsCommand):
        body = body.as_command()
    app_state.require_current_session().put_control_request(
        body,
        from_consumer_id=ConsumerId(app_state.require_current_session_id()),
    )
    return SuccessResponse()


def parse_title(filepath: str | None) -> str:
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


async def install_packages_on_server(
    manager: str,
    versions: dict[str, str],
) -> None:
    """Install packages into the server's own Python environment.

    Used when the server itself needs a package (e.g. nbformat for
    IPYNB auto-export when running with --sandbox).
    """
    import sys

    from marimo._runtime.packages.package_managers import (
        create_package_manager,
    )

    pkg_manager = create_package_manager(manager, python_exe=sys.executable)
    if not pkg_manager.is_manager_installed():
        pkg_manager.alert_not_installed()
        return
    for pkg, version in versions.items():
        await pkg_manager.install(pkg, version=version or None)


def notify_server_missing_packages(
    session: Session | None,
    session_id: str | None,
    packages: list[str],
) -> None:
    """Send a missing-package alert for a server-side package.

    Uses isolated=True so the install button always appears regardless of
    whether the server is in a virtual environment.
    """
    if session_id is None or session is None:
        return
    from marimo._messaging.notification import MissingPackageAlertNotification
    from marimo._session.utils import send_message_to_consumer

    send_message_to_consumer(
        session=session,
        operation=MissingPackageAlertNotification(
            packages=packages,
            isolated=True,
            source="server",
        ),
        consumer_id=ConsumerId(session_id),
    )
