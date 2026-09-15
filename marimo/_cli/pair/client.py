# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

from marimo._server.api.utils import format_url_host
from marimo._server.server_registry import _servers_dir

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from http.client import HTTPResponse
    from pathlib import Path
    from typing import TextIO


class PairError(Exception):
    """A failure that the CLI reports on stderr with exit status 1."""


@dataclass(frozen=True)
class SSEEvent:
    name: str
    data: str


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    output: str


def load_token(
    token_file: Path | None, environ: Mapping[str, str]
) -> str | None:
    if token_file is None:
        return environ.get("MARIMO_TOKEN") or None

    try:
        token = token_file.read_text(encoding="utf-8").rstrip("\r\n")
    except (OSError, UnicodeError) as error:
        raise PairError("Could not read the token file.") from error
    if not token:
        raise PairError("The token file is empty.")
    return token


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
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname is None:
        raise PairError("The server URL must use http or https.")

    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    try:
        connection = connection_type(
            parsed.hostname,
            parsed.port,
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
    except (OSError, ValueError) as error:
        raise PairError("Could not connect to the server.") from error

    if response.status in (401, 403):
        response.close()
        raise PairError("Authentication failed.")
    if not 200 <= response.status < 300:
        response.close()
        raise PairError(f"Server returned {response.status}.")
    return response


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
    parsed = urlsplit(url)
    request_url = parsed._replace(
        path=f"{parsed.path.rstrip('/')}/api/kernel/execute"
    ).geturl()
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

    def write_buffered_output() -> None:
        if stream:
            return
        stdout.write("".join(stdout_parts))
        stderr.write("".join(stderr_parts))

    try:
        try:
            for event in iter_sse(response):
                payload = json.loads(event.data)
                if event.name == "stdout":
                    write_event(stdout, stdout_parts, payload["data"])
                elif event.name == "stderr":
                    write_event(stderr, stderr_parts, payload["data"])
                elif event.name == "done":
                    write_buffered_output()
                    output = payload["output"]["data"]
                    if output:
                        stdout.write(f"{output}\n")
                    return ExecutionResult(
                        success=payload["success"], output=output
                    )
        except (OSError, http.client.HTTPException) as error:
            write_buffered_output()
            raise PairError(
                "The execution response ended before completion was confirmed."
            ) from error

        write_buffered_output()
        raise PairError(
            "The execution response ended before completion was confirmed."
        )
    finally:
        response.close()


def list_sessions(
    *, url: str, token: str | None
) -> dict[str, dict[str, str | None]]:
    request_url = f"{url.rstrip('/')}/api/sessions"
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
        sessions = json.load(response)
    finally:
        response.close()

    if not isinstance(sessions, dict):
        raise PairError(f"Unexpected response from {request_url}.")
    return cast(dict[str, dict[str, str | None]], sessions)


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
