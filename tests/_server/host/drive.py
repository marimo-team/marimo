# Copyright 2026 Marimo. All rights reserved.
"""Drives the host API over ASGI, so tests can read streams as they fill.

The TestClient buffers whole responses, which never works for a stream
that stays open. `request` speaks ASGI directly and returns a `Response`
that collects records as they arrive, with the connection's `client` and
`Host` header set the way the host API requires.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from marimo._server.host import HOST_API_PATH

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from starlette.applications import Starlette

    from marimo._host.host import Host
    from marimo._types.ids import NotebookId

PORT = 1234
"""The port the test server state claims; the Host header must match it."""

AUTHORITY = f"127.0.0.1:{PORT}"


class Response:
    def __init__(self) -> None:
        self.status = 0
        self.headers: dict[str, str] = {}
        self.records: list[dict[str, Any]] = []
        self.body = b""
        self.finished = asyncio.Event()
        self._buffer = ""

    def feed(self, chunk: bytes) -> None:
        self.body += chunk
        self._buffer += chunk.decode()
        while "\n\n" in self._buffer:
            raw, self._buffer = self._buffer.split("\n\n", 1)
            self.records.append(parse(raw))

    def json(self) -> Any:
        return json.loads(self.body)


def parse(raw: str) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for line in raw.split("\n"):
        if line.startswith(":"):
            record["comment"] = line[1:].strip()
        elif ":" in line:
            field, _, value = line.partition(":")
            record[field] = value.strip()
    if "data" in record:
        record["data"] = json.loads(record["data"])
    return record


def request(
    app: Starlette,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
    query: str = "",
) -> tuple[Response, asyncio.Task[None], Callable[[], None]]:
    """Issues one request and returns its response, task, and a disconnect.

    `path` is relative to the host API's prefix.
    """
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": HOST_API_PATH + path,
        "raw_path": (HOST_API_PATH + path).encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [
            (b"host", AUTHORITY.encode()),
            (b"content-type", b"application/json"),
            *(
                (k.lower().encode(), v.encode())
                for k, v in (headers or {}).items()
            ),
        ],
        "client": ("127.0.0.1", 50000),
        "server": ("127.0.0.1", PORT),
        "app": app,
        "state": {},
    }
    response = Response()
    receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    receive_queue.put_nowait(
        {"type": "http.request", "body": body, "more_body": False}
    )

    async def receive() -> dict[str, Any]:
        return await receive_queue.get()

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            response.status = message["status"]
            response.headers = {
                k.decode(): v.decode() for k, v in message.get("headers", [])
            }
        elif message["type"] == "http.response.body":
            response.feed(message.get("body", b""))
            if not message.get("more_body"):
                response.finished.set()

    task = asyncio.create_task(app(scope, receive, send))  # type: ignore[arg-type]

    def disconnect() -> None:
        receive_queue.put_nowait({"type": "http.disconnect"})
        task.cancel()

    return response, task, disconnect


async def finished(
    app: Starlette,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
    query: str = "",
) -> Response:
    """Issues a request that completes and returns its response."""
    response, task, _ = request(
        app, method, path, headers=headers, body=body, query=query
    )
    # Wait on the task as well, so a handler that crashes before finishing
    # its response fails here with its traceback, not with a timeout.
    waiter = asyncio.ensure_future(response.finished.wait())
    try:
        done, _ = await asyncio.wait(
            {waiter, task}, timeout=30, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        waiter.cancel()
    if not done:
        raise AssertionError(f"Timed out waiting for {method} {path}")
    await task
    return response


def notebook_id(host: Host, path: Path) -> NotebookId:
    """The id the host publishes for the notebook at this relative path."""
    for notebook in host.state.notebooks.values():
        if notebook.path == path:
            return notebook.id
    raise AssertionError(f"No notebook at {path}")


async def wait_for(
    condition: Callable[[], bool], *, timeout: float = 20
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("Timed out waiting for condition")
        await asyncio.sleep(0.05)
