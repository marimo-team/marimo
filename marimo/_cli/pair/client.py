# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ipaddress
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, cast
from urllib.parse import parse_qsl, urlsplit, urlunsplit

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from http.client import HTTPMessage
    from pathlib import Path

ErrorKind = Literal[
    "invalid_target",
    "insecure_http",
    "authentication_failed",
    "connection_failed",
    "no_server",
    "ambiguous_server",
    "no_session",
    "session_not_found",
    "ambiguous_session",
    "invalid_response",
    "incomplete_response",
    "kernel_failure",
    "indeterminate_result",
    "broken_pipe",
    "version_unavailable",
]
Origin = Literal["local", "windows-host", "direct"]


class PairError(Exception):
    def __init__(self, kind: ErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


@dataclass(frozen=True)
class PairServer:
    server_id: str
    origin: Origin
    url: str | None
    started_at: str
    version: str


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    filename: str | None
    path: str | None


@dataclass(frozen=True)
class ResolvedTarget:
    server: PairServer
    session: SessionInfo
    version: str


class HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def read(self, size: int = -1) -> bytes: ...

    def close(self) -> None: ...


class HttpTransport(Protocol):
    def open(
        self,
        request: urllib.request.Request,
        *,
        timeout: float | None,
    ) -> HttpResponse: ...


def load_token(
    *,
    token_file: Path | None,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    if token_file is None:
        current_environ = os.environ if environ is None else environ
        return current_environ.get("MARIMO_TOKEN") or None

    try:
        token = token_file.read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError) as error:
        raise PairError(
            "invalid_target",
            "Could not read the token file.",
        ) from error
    if not token:
        raise PairError("invalid_target", "The token file is empty.")
    return token


def resolve_server(
    *,
    url: str | None,
    discovered: Sequence[PairServer],
    allow_insecure_http: bool,
) -> PairServer:
    if url is not None:
        _validate_url(url, allow_insecure_http=allow_insecure_http)
        return PairServer(
            server_id=url,
            origin="direct",
            url=url,
            started_at="",
            version="",
        )

    reachable = tuple(
        server for server in discovered if server.url is not None
    )
    if not reachable:
        raise PairError("no_server", "No reachable marimo server was found.")
    if len(reachable) > 1:
        raise PairError(
            "ambiguous_server",
            "More than one reachable marimo server was found.",
        )
    return reachable[0]


def _validate_url(url: str, *, allow_insecure_http: bool) -> None:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise PairError(
            "invalid_target", "The server URL is invalid."
        ) from error

    if parsed.scheme not in ("http", "https") or parsed.hostname is None:
        raise PairError("invalid_target", "The server URL is invalid.")
    if parsed.username is not None or parsed.password is not None:
        raise PairError(
            "invalid_target",
            "The server URL must not contain credentials.",
        )
    credential_keys = {"auth", "token", "access_token"}
    if any(
        key.lower() in credential_keys
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise PairError(
            "invalid_target",
            "The server URL must not contain credentials.",
        )
    if parsed.scheme == "http" and not allow_insecure_http:
        host = parsed.hostname
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = host.lower() == "localhost"
        if not is_loopback:
            raise PairError(
                "insecure_http",
                "A remote server cannot use plain HTTP without an override.",
            )
    del port


def _origin(url: str) -> tuple[str, str, int | None]:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise PairError(
            "invalid_target", "The redirect URL is invalid."
        ) from error
    if parsed.hostname is None:
        raise PairError("invalid_target", "The redirect URL is invalid.")
    if port is None:
        port = {"http": 80, "https": 443}.get(parsed.scheme.lower())
    return parsed.scheme.lower(), parsed.hostname.lower(), port


class SameOriginRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        if request.get_header("Authorization") is not None and _origin(
            request.full_url
        ) != _origin(newurl):
            raise PairError(
                "invalid_target",
                "An authenticated request cannot follow a cross-origin redirect.",
            )
        return super().redirect_request(
            request,
            fp,  # type: ignore[arg-type]
            code,
            msg,
            headers,
            newurl,
        )


class _UrllibTransport:
    def __init__(self) -> None:
        self._opener = urllib.request.build_opener(SameOriginRedirectHandler())

    def open(
        self,
        request: urllib.request.Request,
        *,
        timeout: float | None,
    ) -> HttpResponse:
        return cast(HttpResponse, self._opener.open(request, timeout=timeout))


class PairClient:
    def __init__(
        self,
        server: PairServer,
        *,
        token: str | None,
        transport: HttpTransport | None = None,
    ) -> None:
        if server.url is None:
            raise PairError("invalid_target", "The server is not reachable.")
        self._url = server.url
        self._token = token
        self._transport = (
            _UrllibTransport() if transport is None else transport
        )

    def version(self) -> str:
        body = self._get("api/version")
        try:
            version = body.decode("utf-8").rstrip("\r\n")
        except UnicodeDecodeError as error:
            raise PairError(
                "invalid_response",
                "The server returned an invalid version.",
            ) from error
        if not version:
            raise PairError(
                "invalid_response",
                "The server returned an empty version.",
            )
        return version

    def sessions(self) -> tuple[SessionInfo, ...]:
        try:
            payload = json.loads(self._get("api/sessions"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PairError(
                "invalid_response",
                "The server returned invalid session data.",
            ) from error
        if not isinstance(payload, dict):
            raise PairError(
                "invalid_response",
                "The server returned invalid session data.",
            )

        sessions: list[SessionInfo] = []
        for session_id, value in payload.items():
            if not isinstance(session_id, str) or not isinstance(value, dict):
                raise PairError(
                    "invalid_response",
                    "The server returned invalid session data.",
                )
            filename = value.get("filename")
            path = value.get("path")
            if not _is_optional_string(filename) or not _is_optional_string(
                path
            ):
                raise PairError(
                    "invalid_response",
                    "The server returned invalid session data.",
                )
            sessions.append(SessionInfo(session_id, filename, path))
        return tuple(sessions)

    def resolve_session(
        self,
        *,
        session_id: str | None,
        notebook: str | None,
    ) -> SessionInfo:
        if session_id is not None and notebook is not None:
            raise PairError(
                "invalid_target",
                "Use either a session ID or a notebook, not both.",
            )
        sessions = self.sessions()
        if session_id is not None:
            matches = tuple(
                session
                for session in sessions
                if session.session_id == session_id
            )
        elif notebook is not None:
            matches = tuple(
                session
                for session in sessions
                if notebook in (session.filename, session.path)
            )
        else:
            if not sessions:
                raise PairError("no_session", "The server has no sessions.")
            if len(sessions) > 1:
                raise PairError(
                    "ambiguous_session",
                    "The server has more than one session.",
                )
            return sessions[0]

        if not matches:
            raise PairError("session_not_found", "The session was not found.")
        if len(matches) > 1:
            raise PairError(
                "ambiguous_session",
                "More than one session matches the notebook.",
            )
        return matches[0]

    def _get(self, endpoint: str) -> bytes:
        parsed = urlsplit(self._url)
        path = f"{parsed.path.rstrip('/')}/{endpoint}"
        url = urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
        headers = {}
        if self._token is not None:
            headers["Authorization"] = f"Bearer {self._token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            response = self._transport.open(request, timeout=5.0)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                raise PairError(
                    "authentication_failed",
                    "The server rejected authentication.",
                ) from error
            raise PairError(
                "connection_failed",
                "The server request failed.",
            ) from error
        except PairError:
            raise
        except (OSError, urllib.error.URLError) as error:
            raise PairError(
                "connection_failed",
                "Could not connect to the server.",
            ) from error

        try:
            if response.status in (401, 403):
                raise PairError(
                    "authentication_failed",
                    "The server rejected authentication.",
                )
            if not 200 <= response.status < 300:
                raise PairError(
                    "connection_failed",
                    "The server request failed.",
                )
            return response.read()
        finally:
            response.close()


def _is_optional_string(value: object) -> bool:
    return value is None or isinstance(value, str)
