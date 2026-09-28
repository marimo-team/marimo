# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from marimo._server.api.utils import format_url_host
from marimo._server.server_registry import _servers_dir

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from http.client import HTTPResponse
    from pathlib import Path
    from typing import TextIO


class PairError(Exception):
    """A failure that the CLI reports on stderr."""


class PairInputError(PairError):
    """Invalid local input that prevents a server operation."""


class NoSessionError(PairError):
    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url


class AmbiguousSessionError(PairError):
    def __init__(
        self, message: str, *, url: str, candidates: tuple[str, ...]
    ) -> None:
        super().__init__(message)
        self.url = url
        self.candidates = candidates


class StaleSessionError(PairError):
    """The server rejected the session ID as unknown."""


@dataclass(frozen=True)
class SSEEvent:
    name: str
    data: str


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    output: dict[str, str] | None
    stdout: str
    stderr: str


def load_token(
    token_file: Path | None, environ: Mapping[str, str]
) -> str | None:
    if token_file is None:
        return environ.get("MARIMO_TOKEN") or None

    try:
        token = token_file.read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError) as error:
        raise PairInputError("Could not read the token file.") from error
    if not token:
        raise PairInputError("The token file is empty.")
    return token


def display_url(url: str) -> str:
    """Return a URL without credentials, query values, or a fragment."""
    try:
        parsed = urlsplit(url)
    except ValueError:
        return "<invalid URL>"
    return parsed._replace(
        netloc=parsed.netloc.rsplit("@", 1)[-1], query="", fragment=""
    ).geturl()


def _endpoint_url(url: str, path: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise PairInputError("The server URL is invalid.") from error
    return parsed._replace(
        path=f"{parsed.path.rstrip('/')}{path}", fragment=""
    ).geturl()


def iter_sse(lines: Iterable[bytes]) -> Iterator[SSEEvent]:
    name = "message"
    data: list[str] = []

    for raw_line in lines:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                yield SSEEvent(name=name, data="\n".join(data))
            name = "message"
            data = []
            continue
        if line.startswith(":"):
            continue

        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            name = value
        elif field == "data":
            data.append(value)

    if data:
        yield SSEEvent(name=name, data="\n".join(data))


def open_response(
    *, method: str, url: str, headers: dict[str, str], body: bytes | None
) -> HTTPResponse:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise PairInputError("The server URL is invalid.") from error
    if parsed.scheme not in ("http", "https") or parsed.hostname is None:
        raise PairInputError("The server URL must use http or https.")
    if port is not None and not 1 <= port <= 65535:
        raise PairInputError("The server URL is invalid.")

    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    try:
        connection = connection_type(
            parsed.hostname,
            port,
            timeout=5.0,
        )
        connection.connect()
        if connection.sock is not None:
            connection.sock.settimeout(None)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
    except (ValueError, http.client.InvalidURL) as error:
        raise PairInputError("The server URL is invalid.") from error
    except (OSError, http.client.HTTPException) as error:
        raise PairError("Could not connect to the server.") from error

    _raise_for_status(response)
    return response


def _response_detail(response: HTTPResponse) -> str | None:
    try:
        payload = json.loads(response.read())
    except (OSError, UnicodeError, ValueError, http.client.HTTPException):
        return None
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
    return None


def _raise_for_status(response: HTTPResponse) -> None:
    if response.status in (401, 403):
        response.close()
        raise PairError("Authentication failed.")
    if 200 <= response.status < 300:
        return
    detail = _response_detail(response)
    response.close()
    if isinstance(detail, str) and detail.startswith("Invalid session id"):
        raise StaleSessionError(detail)
    if detail == "Missing Marimo-Session-Id header":
        raise PairError("Internal: should not happen after resolution.")
    if detail:
        raise PairError(detail)
    raise PairError(f"Server returned {response.status}.")


def execute(
    *,
    url: str,
    session_id: str,
    token: str | None,
    code: str,
    stdout: TextIO,
    stderr: TextIO,
    stream: bool,
) -> ExecutionResult:
    request_url = _endpoint_url(url, "/api/kernel/execute")
    headers = {
        "Content-Type": "application/json",
        "Marimo-Session-Id": session_id,
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps({"code": code}).encode("utf-8")
    response = open_response(
        method="POST",
        url=request_url,
        headers=headers,
        body=body,
    )
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    def write_event(target: TextIO, parts: list[str], value: str) -> None:
        if stream:
            target.write(value)
            target.flush()
        else:
            parts.append(value)

    try:
        try:
            for event in iter_sse(response):
                payload = json.loads(event.data)
                if event.name == "stdout":
                    write_event(stdout, stdout_parts, payload["data"])
                elif event.name == "stderr":
                    write_event(stderr, stderr_parts, payload["data"])
                elif event.name == "done":
                    raw_output = payload.get("output")
                    data = ""
                    mimetype = "text/plain"
                    if isinstance(raw_output, dict):
                        data = str(raw_output.get("data") or "")
                        mimetype = str(
                            raw_output.get("mimetype") or "text/plain"
                        )
                    output = (
                        None
                        if not data
                        else {"mimetype": mimetype, "data": data}
                    )
                    if stream and output is not None:
                        stdout.write(f"{output['data']}\n")
                    return ExecutionResult(
                        success=bool(payload["success"]),
                        output=output,
                        stdout="".join(stdout_parts),
                        stderr="".join(stderr_parts),
                    )
        except (
            OSError,
            http.client.HTTPException,
            ValueError,
            KeyError,
            TypeError,
        ) as error:
            # A malformed event means the outcome is unknown. The code may
            # have run, so the caller must inspect rather than retry.
            raise PairError(
                "The execution response ended before completion was confirmed."
            ) from error

        raise PairError(
            "The execution response ended before completion was confirmed."
        )
    finally:
        response.close()


def list_sessions(
    *, url: str, token: str | None
) -> dict[str, dict[str, str | None]]:
    request_url = _endpoint_url(url, "/api/sessions")
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    response = open_response(
        method="GET",
        url=request_url,
        headers=headers,
        body=None,
    )
    try:
        try:
            payload = json.load(response)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            http.client.HTTPException,
        ) as error:
            raise PairError(
                f"Unexpected response from {display_url(request_url)}."
            ) from error
    finally:
        response.close()

    message = f"Unexpected response from {display_url(request_url)}."
    if not isinstance(payload, dict):
        raise PairError(message)

    sessions: dict[str, dict[str, str | None]] = {}
    for session_id, session in payload.items():
        if not isinstance(session_id, str) or not isinstance(session, dict):
            raise PairError(message)
        if "filename" not in session or "path" not in session:
            raise PairError(message)
        filename = session["filename"]
        path = session["path"]
        if (filename is not None and not isinstance(filename, str)) or (
            path is not None and not isinstance(path, str)
        ):
            raise PairError(message)
        sessions[session_id] = {"filename": filename, "path": path}
    return sessions


def resolve_session(*, url: str, token: str | None, file: str | None) -> str:
    sessions = list_sessions(url=url, token=token)
    safe_url = display_url(url)
    if file is None:
        candidates = list(sessions)
    else:
        for field, value in (
            ("path", file),
            ("filename", file),
            ("path", os.path.abspath(file)),
        ):
            candidates = [
                session_id
                for session_id, session in sessions.items()
                if session[field] == value
            ]
            if candidates:
                break

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        if file is None:
            message = f"No running session on {safe_url}."
        else:
            message = (
                f"No running session for notebook '{file}' on {safe_url}."
            )
        raise NoSessionError(message, url=safe_url)

    candidates.sort()
    if file is None:
        message = f"Server {safe_url} has {len(candidates)} running sessions."
    else:
        message = (
            f"Notebook '{file}' has {len(candidates)} running sessions "
            f"on {safe_url}."
        )
    raise AmbiguousSessionError(
        message, url=safe_url, candidates=tuple(candidates)
    )


def registry_urls() -> list[str]:
    import psutil

    urls: list[str] = []
    for path in sorted(_servers_dir().glob("*.json")):
        try:
            with path.open(encoding="utf-8") as file:
                entry = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(entry, dict):
            continue
        pid = entry.get("pid")
        host = entry.get("host")
        port = entry.get("port")
        base_url = entry.get("base_url")
        if (
            type(pid) is not int
            or not psutil.pid_exists(pid)
            or not isinstance(host, str)
            or type(port) is not int
            or not 1 <= port <= 65535
            or not isinstance(base_url, str)
        ):
            continue

        url_host = format_url_host(host, port, route_bind_all_to_loopback=True)
        if port == 80:
            urls.append(f"http://{url_host}{base_url}")
        elif port == 443:
            urls.append(f"https://{url_host}{base_url}")
        else:
            urls.append(f"http://{url_host}:{port}{base_url}")
    return urls
