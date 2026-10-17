# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import http.client
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, TypeVar
from urllib.parse import quote, urlencode, urlsplit

import msgspec

from marimo._cli.pair.client import PairError, PairInputError
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle

if TYPE_CHECKING:
    from collections.abc import Mapping

T = TypeVar("T")
_SETUP = (
    "OpenCode agent messages require OpenCode 2.x. "
    "Run connect in a native OpenCode 2.x shell with a registered local service."
)


def _request(
    url: str,
    authorization: str | None,
    result_type: type[T],
    *,
    text: str | None = None,
) -> T:
    try:
        endpoint = urlsplit(url)
        port = endpoint.port
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
    connection = http.client.HTTPConnection(
        endpoint.hostname, port, timeout=10
    )
    headers = {"Content-Type": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    try:
        body = (
            None
            if text is None
            else msgspec.json.encode({"text": text, "delivery": "queue"})
        )
        path = endpoint.path + ("?" + endpoint.query if endpoint.query else "")
        connection.request(
            "GET" if text is None else "POST", path, body, headers
        )
        response = connection.getresponse()
        if response.status != 200:
            raise PairError(
                "OpenCode rejected the inbox request. Check the session and credentials."
            )
        data = response.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise PairError("OpenCode returned an oversized inbox response.")
        return msgspec.json.decode(data, type=result_type)
    except (
        OSError,
        http.client.HTTPException,
        ValueError,
        msgspec.DecodeError,
    ) as error:
        raise PairError("Could not reach the OpenCode inbox.") from error
    finally:
        connection.close()


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


class OpenCodeHarness:
    """Verify an OpenCode 2.x session from native identity or its shell PID."""

    kind = "opencode"

    def identity(self, env: Mapping[str, str]) -> str | None:
        try:
            target = self.detect(env)
        except PairError:
            return None
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
            env.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
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
        self.check()
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

    def send(self, text: str) -> None:
        _request(self.target.address, self.target.auth_token, dict, text=text)

    def alive(self) -> bool:
        return self.target.process is not None and self.target.process.alive()
