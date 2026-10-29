# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import json
import queue
import signal
import socket
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import quote, urlsplit
from uuid import uuid4

from marimo._server.api.utils import format_url_host
from marimo._server.host import (
    ATTACHMENT_IDENTITY,
    ATTACHMENT_KIND,
    ATTACHMENT_NAME,
    HOST_API_PATH,
)
from marimo._server.server_registry import _servers_dir

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from http.client import HTTPResponse
    from pathlib import Path
    from types import FrameType
    from typing import TextIO


class PairError(Exception):
    """A failure that the CLI reports on stderr."""


class PairInputError(PairError):
    """Invalid local input that prevents a server operation."""


class PairConnectionError(PairError):
    """A transport failure while connecting to the notebook server."""


class NoRuntimeError(PairError):
    """The notebook has no running kernel."""


class RunConflictError(PairError):
    """The notebook already has an active run."""


class NoNotebookError(PairError):
    """No notebook was found at the requested server URL."""

    def __init__(self, message: str, *, url: str) -> None:
        super().__init__(message)
        self.url = url


class AmbiguousNotebookError(PairError):
    """Discovery found several notebooks and requires an explicit selection."""

    def __init__(
        self, message: str, *, url: str, candidates: tuple[str, ...]
    ) -> None:
        super().__init__(message)
        self.url = url
        self.candidates = candidates


class StaleNotebookError(PairError):
    """The server rejected the Notebook ID as unknown."""


class NotebookUnsupportedError(PairError):
    """The server discovery does not expose host notebooks."""


@dataclass(frozen=True)
class SSEEvent:
    """A parsed server-sent event with an optional stream resume cursor."""

    name: str
    data: str
    id: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """Captured output and final outcome of a notebook execution."""

    success: bool
    output: dict[str, str] | None
    stdout: str
    stderr: str
    outcome: str = "succeeded"


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


def iter_sse(
    lines: Iterable[bytes], *, heartbeats: bool = False
) -> Iterator[SSEEvent]:
    name = "message"
    data: list[str] = []
    cursor: str | None = None

    for raw_line in lines:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if data:
                yield SSEEvent(name=name, data="\n".join(data), id=cursor)
            name = "message"
            data = []
            continue
        if line.startswith(":"):
            if heartbeats:
                yield SSEEvent(name="heartbeat", data="")
            continue

        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            name = value
        elif field == "id" and "\0" not in value:
            cursor = value
        elif field == "data":
            data.append(value)

    if data:
        yield SSEEvent(name=name, data="\n".join(data), id=cursor)


def pump_events(
    events: Iterable[SSEEvent],
    incoming: queue.Queue[SSEEvent | Exception | None],
    stopped: threading.Event,
) -> None:
    """Read events on a worker thread with bounded, cancellable delivery."""

    def put(value: SSEEvent | Exception | None) -> None:
        while not stopped.is_set():
            try:
                incoming.put(value, timeout=0.1)
                return
            except queue.Full:
                continue

    try:
        for event in events:
            if stopped.is_set():
                return
            put(event)
    except (
        PairError,
        OSError,
        http.client.HTTPException,
        ValueError,
        AttributeError,
    ) as error:
        put(error)
    finally:
        put(None)


def open_response(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    read_timeout: float | None = None,
) -> EventStream:
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
        if connection.sock is None:
            raise RuntimeError("Connection socket is not available")
        response_socket = connection.sock
        response_socket.settimeout(read_timeout)
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
    except (ValueError, http.client.InvalidURL) as error:
        connection.close()
        raise PairInputError("The server URL is invalid.") from error
    except (OSError, http.client.HTTPException) as error:
        connection.close()
        raise PairConnectionError(
            "Could not connect to the server."
        ) from error

    try:
        _raise_for_status(response)
    except PairError:
        connection.close()
        raise
    return EventStream(response, response_socket)


def _response_problem(response: HTTPResponse) -> tuple[str | None, str | None]:
    try:
        payload = json.loads(response.read())
    except (OSError, UnicodeError, ValueError, http.client.HTTPException):
        return None, None
    if isinstance(payload, dict):
        detail = payload.get("detail")
        problem = payload.get("type")
        return (
            detail if isinstance(detail, str) else None,
            problem if isinstance(problem, str) else None,
        )
    return None, None


def _raise_for_status(response: HTTPResponse) -> None:
    if response.status in (401, 403):
        response.close()
        raise PairError("Authentication failed.")
    if 200 <= response.status < 300:
        return
    detail, problem = _response_problem(response)
    response.close()
    if isinstance(detail, str) and detail.startswith(
        ("Invalid session id", "Invalid stable session id")
    ):
        raise StaleNotebookError(detail)
    if detail == "Missing Marimo-Session-Id header":
        raise NotebookUnsupportedError
    if response.status == 404:
        raise StaleNotebookError(detail or "Unknown notebook.")
    if problem == "tag:marimo.io,2026:host/no-runtime":
        raise NoRuntimeError(detail or "The notebook has no running kernel.")
    if problem == "tag:marimo.io,2026:host/conflict":
        raise RunConflictError(
            detail or "The notebook already has an active run."
        )
    if detail:
        raise PairError(detail)
    raise PairError(f"Server returned {response.status}.")


def execute(
    *,
    url: str,
    notebook_id: str,
    token: str,
    code: str,
    stdout: TextIO,
    stderr: TextIO,
    stream: bool,
) -> ExecutionResult:
    response = open_events(
        url=url,
        notebook=notebook_id,
        token=token,
        identity=str(uuid4()),
        name="pair execute",
        kind="client",
        types="run,execution,console",
        read_timeout=45,
    )
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []
    executions: set[str] = set()
    output: dict[str, str] | None = None
    run_url = _endpoint_url(
        url, f"/notebooks/{quote(notebook_id, safe='')}/runtime/runs"
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    def mutation(
        method: str, endpoint: str, body: bytes | None = None
    ) -> object:
        reply = open_response(
            method=method,
            url=endpoint,
            headers={**headers, "Idempotency-Key": str(uuid4())},
            body=body,
        )
        try:
            return json.load(reply.response)
        finally:
            reply.close()

    def write(target: TextIO, parts: list[str], value: str) -> None:
        if stream:
            target.write(value)
            target.flush()
        else:
            parts.append(value)

    stopped = threading.Event()
    interrupted = threading.Event()
    interrupt_sent = False
    reader: threading.Thread | None = None
    previous_handler = None

    def request_interrupt(_signum: int, _frame: FrameType | None) -> None:
        interrupted.set()

    try:
        events = iter_sse(response)
        for initial_event in events:
            if initial_event.name == "ready":
                break
        else:
            raise PairError("The notebook stream ended before it was ready.")
        if threading.current_thread() is threading.main_thread():
            previous_handler = signal.signal(signal.SIGINT, request_interrupt)
        started = mutation(
            "POST", run_url, json.dumps({"code": code}).encode()
        )
        if not isinstance(started, dict) or not isinstance(
            started.get("id"), str
        ):
            raise PairError("The server returned an invalid run.")
        run_id = str(started["id"])
        incoming: queue.Queue[SSEEvent | Exception | None] = queue.Queue(
            maxsize=64
        )

        reader = threading.Thread(
            target=pump_events, args=(events, incoming, stopped), daemon=True
        )
        reader.start()
        while True:
            if interrupted.is_set() and not interrupt_sent:
                interrupt_sent = True
                try:
                    mutation("DELETE", f"{run_url}/{quote(run_id, safe='')}")
                except RunConflictError:
                    # Completion can win the race with the interrupt request.
                    pass
            try:
                event = incoming.get(timeout=0.1)
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                interrupted.set()
                continue
            if event is None:
                raise StopIteration
            if isinstance(event, BaseException):
                raise event
            payload = json.loads(event.data)
            if event.name == "execution":
                execution = payload["execution"]
                if execution.get("run_id") != run_id:
                    continue
                executions.add(execution["id"])
                outcome = execution.get("outcome")
                if isinstance(outcome, dict):
                    if outcome.get("kind") == "value":
                        output = outcome.get("display")
                    elif (
                        outcome.get("kind") == "error"
                        and execution.get("status") == "completed"
                    ):
                        error = outcome["error"]
                        traceback = error.get("traceback")
                        if (
                            isinstance(traceback, dict)
                            and traceback.get("mimetype") == "text/plain"
                        ):
                            text = traceback["data"]
                        else:
                            name = error.get("name")
                            text = (
                                f"{name}: {error['message']}"
                                if name
                                else error["message"]
                            )
                        write(stderr, stderr_parts, text.rstrip("\n") + "\n")
            elif event.name == "console":
                console = payload["console"]
                if console["execution_id"] in executions:
                    if console["name"] == "stdout":
                        write(stdout, stdout_parts, console["text"])
                    else:
                        write(stderr, stderr_parts, console["text"])
            elif event.name == "run":
                run = payload["run"]
                if run["id"] == run_id and run["status"] == "completed":
                    if stream and output is not None:
                        stdout.write(f"{output['data']}\n")
                    if run["outcome"] not in (
                        "succeeded",
                        "failed",
                        "interrupted",
                    ):
                        raise ValueError("Missing run outcome")
                    return ExecutionResult(
                        success=run["outcome"] == "succeeded",
                        output=output,
                        stdout="".join(stdout_parts),
                        stderr="".join(stderr_parts),
                        outcome=run["outcome"],
                    )
    except (
        StopIteration,
        PairConnectionError,
        OSError,
        http.client.HTTPException,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
    ) as error:
        raise PairError(
            "The execution response ended before completion was confirmed."
        ) from error
    finally:
        if previous_handler is not None:
            signal.signal(signal.SIGINT, previous_handler)
        stopped.set()
        response.close()
        if reader is not None:
            reader.join(timeout=1)


def execute_editor(
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
        "Marimo-Stable-Session-Id": session_id,
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps({"code": code}).encode("utf-8")
    try:
        response = open_response(
            method="POST", url=request_url, headers=headers, body=body
        )
    except PairConnectionError as error:
        raise PairError(
            "The execution response ended before completion was confirmed."
        ) from error
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
                        outcome="succeeded"
                        if payload["success"]
                        else "failed",
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


@dataclass(frozen=True)
class EventStream:
    """An HTTP response whose socket can be closed to unblock its reader."""

    response: HTTPResponse
    socket: socket.socket

    def __iter__(self) -> Iterator[bytes]:
        return iter(self.response)

    def close(self) -> None:
        # Shutdown interrupts a blocked reader before closing its file handle.
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.response.close()
        finally:
            self.socket.close()


def open_events(
    *,
    url: str,
    notebook: str,
    token: str | None,
    identity: str,
    name: str,
    cursor: str | None = None,
    kind: str = "agent",
    types: str = "custom,attachment",
    read_timeout: float | None = 45,
) -> EventStream:
    headers = {
        ATTACHMENT_IDENTITY: identity,
        ATTACHMENT_KIND: kind,
        ATTACHMENT_NAME: name,
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if cursor is not None:
        headers["Last-Event-ID"] = cursor
    return open_response(
        method="GET",
        url=_endpoint_url(url, f"/notebooks/{quote(notebook, safe='')}/events")
        + f"?types={types}",
        headers=headers,
        body=None,
        read_timeout=read_timeout,
    )


@dataclass(frozen=True)
class HostEndpoint:
    """Host API address and bearer token from a validated live host record."""

    url: str
    token: str = field(repr=False)


def resolve_host(url: str, *, root: Path | None = None) -> HostEndpoint:
    import os
    import stat

    import msgspec
    import psutil

    from marimo._core import protocol
    from marimo._utils.xdg import marimo_state_dir

    def normalized(value: str) -> tuple[str, str | None, int, str]:
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or parsed.hostname is None:
            raise PairInputError("The server URL must use http or https.")
        host = parsed.hostname.lower()
        if host == "localhost":
            host = "127.0.0.1"
        path = parsed.path.rstrip("/")
        path = path.removesuffix(HOST_API_PATH)
        return (
            parsed.scheme,
            host,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            path,
        )

    try:
        selected = normalized(url)
    except ValueError as error:
        raise PairInputError("The server URL is invalid.") from error
    directory = root if root is not None else marimo_state_dir() / "hosts-v1"
    for path in sorted(directory.glob("*.json")):
        try:
            descriptor = os.open(
                path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
            )
            with os.fdopen(descriptor, "rb") as record_file:
                info = os.fstat(record_file.fileno())
                if not stat.S_ISREG(info.st_mode):
                    continue
                if os.name == "posix" and (
                    info.st_uid != os.getuid() or info.st_mode & 0o077
                ):
                    continue
                record = msgspec.json.decode(
                    record_file.read(), type=protocol.HostRecord
                )
            if normalized(record.url) != selected:
                continue
            process = psutil.Process(record.process.pid)
            if (
                not process.is_running()
                or process.status() == psutil.STATUS_ZOMBIE
            ):
                continue
            if (
                abs(
                    process.create_time()
                    - record.process.started_at.timestamp()
                )
                > 1e-6
            ):
                continue
            return HostEndpoint(record.url, record.token)
        except (OSError, ValueError, msgspec.DecodeError, psutil.Error):
            continue
    raise PairError(
        "No live host record matches this URL. Start a local edit server, or restart the existing server."
    )


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
            payload = json.load(response.response)
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
        if "session_id" not in session:
            raise NotebookUnsupportedError
        stable_session_id = session["session_id"]
        filename = session["filename"]
        path = session["path"]
        if (
            not isinstance(stable_session_id, str)
            or (filename is not None and not isinstance(filename, str))
            or (path is not None and not isinstance(path, str))
        ):
            raise PairError(message)
        notebook_id = session.get("notebook_id")
        if notebook_id is not None and not isinstance(notebook_id, str):
            raise PairError(message)
        sessions[session_id] = {
            "session_id": stable_session_id,
            "filename": filename,
            "path": path,
            "notebook_id": notebook_id,
        }
    return sessions


def resolve_notebook(*, url: str, token: str | None) -> str:
    sessions = list_sessions(url=url, token=token)
    candidates = sorted(
        {
            session["notebook_id"]
            for session in sessions.values()
            if session["notebook_id"] is not None
        }
    )
    safe_url = display_url(url)
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise NoNotebookError(
            f"No host notebook on {safe_url}. Save and open the notebook in edit mode.",
            url=safe_url,
        )
    raise AmbiguousNotebookError(
        f"Server {safe_url} has {len(candidates)} notebooks.",
        url=safe_url,
        candidates=tuple(candidates),
    )


def resolve_execution_target(
    *, url: str, token: str | None, session_id: str | None = None
) -> tuple[str | None, str]:
    """Choose a host Notebook or editor Session before submitting code."""
    sessions = list_sessions(url=url, token=token)
    found = [
        value
        for value in sessions.values()
        if session_id is None or value["session_id"] == session_id
    ]
    if not found:
        if session_id is not None:
            raise StaleNotebookError(
                f"Invalid stable session id: {session_id}"
            )
        raise NoNotebookError(
            f"No running session on {display_url(url)}.", url=display_url(url)
        )
    if len(found) != 1:
        raise AmbiguousNotebookError(
            f"Server {display_url(url)} has {len(found)} running sessions.",
            url=display_url(url),
            candidates=tuple(
                sorted(str(value["session_id"]) for value in found)
            ),
        )
    selected = found[0]
    stable_id = selected["session_id"]
    if stable_id is None:
        raise RuntimeError("Selected session has no session ID")
    return selected.get("notebook_id"), stable_id


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
