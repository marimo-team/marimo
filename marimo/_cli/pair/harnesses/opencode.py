# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING, ClassVar, Literal, TypeVar
from urllib.parse import quote, unquote, urlencode, urlsplit

import msgspec

from marimo._cli.pair.client import (
    PairError,
    PairInputError,
    SubmissionRejectedError,
)
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle, Submission
from marimo._utils.requests import RequestError, request

if TYPE_CHECKING:
    from collections.abc import Mapping

T = TypeVar("T")
_REQUEST_TIMEOUT = 10
_SETUP = (
    "OpenCode agent messages require OpenCode 2.x. "
    "Run connect in a native OpenCode 2.x shell with a registered local service."
)


def _check_status(status: int | None, *, submitting: bool) -> None:
    if status in {401, 403}:
        error_type = SubmissionRejectedError if submitting else PairError
        raise error_type(
            "OpenCode refused the inbox request. Check the credentials."
        )
    if status is not None and status != 200:
        raise PairError(
            "OpenCode did not confirm the inbox request. Check the session and credentials."
        )


def _request(
    url: str,
    authorization: str | None,
    result_type: type[T],
    *,
    text: str | None = None,
) -> T:
    deadline = monotonic() + _REQUEST_TIMEOUT
    try:
        endpoint = urlsplit(url)
        _ = endpoint.port
    except ValueError as error:
        raise PairInputError("The OpenCode inbox URL is invalid.") from error
    if (
        endpoint.scheme != "http"
        or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.fragment
    ):
        raise PairInputError(
            "OpenCode delivery requires a local HTTP endpoint."
        )
    headers = {"Content-Type": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    try:
        response = request(
            "GET" if text is None else "POST",
            url,
            data=(
                None
                if text is None
                else msgspec.json.encode({"text": text, "delivery": "queue"})
            ),
            headers=headers,
            deadline=deadline,
            max_response_bytes=1024 * 1024,
        )
    except RequestError as error:
        _check_status(error.status_code, submitting=text is not None)
        if error.dispatched is False:
            error_type = (
                SubmissionRejectedError if text is not None else PairError
            )
            raise error_type(
                "Could not connect to the OpenCode inbox."
            ) from error
        raise PairError("Could not reach the OpenCode inbox.") from error
    _check_status(response.status_code, submitting=text is not None)
    try:
        return msgspec.json.decode(response.content, type=result_type)
    except msgspec.DecodeError as error:
        raise PairError("Could not reach the OpenCode inbox.") from error


@dataclass(frozen=True)
class _Service:
    url: str
    pid: int
    version: str
    password: str | None = field(default=None, repr=False)


class _Info(msgspec.Struct):
    pid: int
    version: str


class _Metadata(msgspec.Struct):
    sessionID: str | None = None


class _Shell(msgspec.Struct):
    metadata: _Metadata
    pid: int | None = None


class _Shells(msgspec.Struct):
    data: list[_Shell]


class _Session(msgspec.Struct):
    id: str


class _SessionResponse(msgspec.Struct):
    data: _Session


class _AdmittedMessage(msgspec.Struct):
    id: str
    type: Literal["user"]
    sessionID: str


class _PromptResponse(msgspec.Struct):
    data: _AdmittedMessage


class OpenCodeHarness:
    """Verify an OpenCode 2.x session from native identity or its shell PID."""

    kind = "opencode"

    def identity(self, env: Mapping[str, str]) -> str | None:
        target = self.detect(env)
        return target.address if target else None

    def detect(
        self, env: Mapping[str, str], *, process: ProcessHandle | None = None
    ) -> DeliveryTarget | None:
        import psutil

        if env.get("OPENCODE_TERMINAL") != "1":
            if env.get("OPENCODE"):
                raise PairInputError(_SETUP)
            return None
        self.check()
        state = Path(
            env.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
        )
        path = state / "opencode" / "service.json"
        try:
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_mode & 0o077
            ):
                raise ValueError
            service = msgspec.json.decode(path.read_bytes(), type=_Service)
            if not service.version.startswith("2.") or service.pid <= 0:
                raise ValueError
            owner = ProcessHandle.capture(service.pid)
        except (
            OSError,
            ValueError,
            msgspec.DecodeError,
            psutil.Error,
        ) as error:
            raise PairInputError(
                "No valid private OpenCode v2 service record. " + _SETUP
            ) from error
        base = service.url.rstrip("/")
        authorization = None
        if service.password is not None:
            authorization = (
                "Basic "
                + base64.b64encode(
                    ("opencode:" + service.password).encode()
                ).decode()
            )
        remote = _request(base + "/api/info", authorization, _Info)
        if remote.pid != service.pid or remote.version != service.version:
            raise PairInputError(
                "The OpenCode service record does not match the running service."
            )
        query = "?" + urlencode({"location[directory]": os.getcwd()})
        session = env.get("OPENCODE_SESSION_ID")
        if not session:
            shells = _request(
                base + "/api/shell" + query, authorization, _Shells
            )
            try:
                ancestors = {
                    os.getpid(),
                    *(parent.pid for parent in psutil.Process().parents()),
                }
            except psutil.Error as error:
                raise PairInputError(
                    "Could not inspect the OpenCode shell process."
                ) from error
            sessions = {
                shell.metadata.sessionID
                for shell in shells.data
                if shell.pid in ancestors and shell.metadata.sessionID
            }
            if len(sessions) != 1:
                raise PairInputError(
                    "Could not identify one OpenCode conversation from the current shell PID. "
                    + _SETUP
                )
            session = sessions.pop()
        if not owner.alive():
            raise PairInputError("The OpenCode inbox owner is not running.")
        address = base + "/api/session/" + quote(session, safe="")
        current = _request(address + query, authorization, _SessionResponse)
        if current.data.id != session:
            raise PairInputError("OpenCode returned a different conversation.")
        return DeliveryTarget(
            self.kind,
            address + "/prompt" + query,
            "OpenCode",
            process or owner,
            authorization,
        )

    def check(self) -> None:
        if os.name == "nt":
            raise PairInputError(
                "OpenCode inbox discovery requires macOS or Linux."
            )

    def open_inbox(self, target: DeliveryTarget) -> OpenCodeInbox:
        return OpenCodeInbox(target)


@dataclass(frozen=True)
class OpenCodeInbox:
    """Queue messages in one verified OpenCode conversation without starting a service."""

    target: DeliveryTarget
    inbox_bytes: ClassVar[int] = 64 * 1024

    def send(self, text: str) -> Submission:
        response = _request(
            self.target.address,
            self.target.auth_token,
            _PromptResponse,
            text=text,
        )
        session_id = unquote(
            urlsplit(self.target.address).path.rsplit("/", 2)[1]
        )
        if not response.data.id or response.data.sessionID != session_id:
            raise PairError("OpenCode returned an invalid admission response.")
        return Submission("submitted", "OpenCode admitted the message.")

    def alive(self) -> bool:
        return self.target.process is not None and self.target.process.alive()
