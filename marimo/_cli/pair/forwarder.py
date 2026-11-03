# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import http.client
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import msgspec

from marimo._cli.pair.artifacts import AgentMessageFiles, inbox_message
from marimo._cli.pair.client import (
    EventStream,
    PairConnectionError,
    PairError,
    SSEEvent,
    StaleNotebookError,
    iter_sse,
    open_events,
    pump_events,
)
from marimo._cli.pair.connection import Connection, ConnectionStore
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.harnesses import harness_for
from marimo._messaging.messages import AGENT_MESSAGE_TYPE
from marimo._utils.subprocess import kill_subprocess

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from marimo._cli.pair.delivery import Inbox

_LOGGER = logging.getLogger(__name__)
_LIVENESS_SECONDS = 15.0
_BURST_SECONDS = 1.0
_RECONNECT_MAX_SECONDS = 5.0


@dataclass(frozen=True)
class ForwarderConfig:
    """One notebook subscription and its destination inbox, including credentials."""

    url: str
    notebook: str
    identity: str
    token: str | None
    target: DeliveryTarget


class _Bootstrap(msgspec.Struct):
    """Private stdin payload for starting a forwarder and locating its record."""

    config: ForwarderConfig
    root: str


class _DetachedOptions(TypedDict, total=False):
    creationflags: int
    start_new_session: bool


def detached_options() -> _DetachedOptions:
    if sys.platform == "win32":
        return {
            "creationflags": subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP
        }
    return {"start_new_session": True}


def start_forwarder(
    config: ForwarderConfig, store: ConnectionStore
) -> Connection:
    import psutil

    if config.target.process is None:
        raise RuntimeError("Forwarder target process is not configured")
    process = subprocess.Popen(
        [sys.executable, "-m", "marimo._cli.pair.forwarder"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        **detached_options(),
    )
    record = None
    handle = None
    try:
        handle = ProcessHandle.capture(process.pid)
        record = Connection(
            version=1,
            identity=config.identity,
            notebook=config.notebook,
            harness_kind=config.target.kind,
            harness_pid=config.target.process.pid,
            harness_start=config.target.process.started,
            forwarder_pid=handle.pid,
            forwarder_start=handle.started,
            created_at=time.time(),
        )
        store.save(record)
        if process.stdin is None:
            raise RuntimeError("Process stdin pipe is not available")
        if process.stdout is None:
            raise RuntimeError("Process stdout pipe is not available")
        output = process.stdout
        # Secrets travel through the private pipe, never argv or a state file.
        process.stdin.write(
            msgspec.json.encode(_Bootstrap(config, str(store.root)))
        )
        process.stdin.close()
        ready: queue.Queue[bytes] = queue.Queue(maxsize=1)
        threading.Thread(
            target=lambda: ready.put(output.readline()), daemon=True
        ).start()
        try:
            line = ready.get(timeout=10)
        except queue.Empty as error:
            raise PairError(
                "The agent message forwarder did not attach within 10 seconds."
            ) from error
        if (
            line not in (b"attached\n", b"attached\r\n")
            or process.poll() is not None
        ):
            raise PairError(
                "The agent message forwarder could not attach. Check the server and token."
            )
        return record
    except (OSError, psutil.Error, PairError):
        if process.poll() is None:
            if handle is not None:
                handle.stop()
            else:
                # Capture can fail before there is a reusable process handle.
                kill_subprocess(process, start_new_session=True)
        if record is not None:
            store.remove(record)
        raise
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        if process.stdout is not None:
            process.stdout.close()


def _read_stream(
    config: ForwarderConfig,
    incoming: queue.Queue[SSEEvent | Exception | None],
    stopped: threading.Event,
    responses: list[EventStream],
    cursor: str | None = None,
) -> None:
    def events() -> Iterator[SSEEvent]:
        response = open_events(
            url=config.url,
            notebook=config.notebook,
            token=config.token,
            identity=config.identity,
            cursor=cursor,
            name=config.target.label,
        )
        responses.append(response)
        try:
            if not stopped.is_set():
                yield from iter_sse(response)
        finally:
            response.close()

    pump_events(events(), incoming, stopped)


def _wait_reconnect(inbox: Inbox, delay: float) -> bool:
    deadline = time.monotonic() + delay
    while inbox.alive():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(remaining, 0.1))
    return False


def run_forwarder(
    config: ForwarderConfig,
    inbox: Inbox,
    *,
    ready: Callable[[], None],
) -> None:
    files = AgentMessageFiles()
    files.cleanup()
    pending = ""
    flush_at = 0.0
    check_at = time.monotonic()
    attached = False
    attachment: str | None = None
    cursor: str | None = None
    reconnect_delay = 0.1

    def flush() -> None:
        nonlocal pending
        if pending:
            inbox.send(pending)
            pending = ""

    while inbox.alive():
        attachment = None
        incoming: queue.Queue[SSEEvent | Exception | None] = queue.Queue(
            maxsize=64
        )
        stopped = threading.Event()
        responses: list[EventStream] = []
        reader = threading.Thread(
            target=_read_stream,
            args=(config, incoming, stopped, responses, cursor),
            daemon=True,
        )
        reader.start()
        reconnect = False
        try:
            while True:
                now = time.monotonic()
                if now >= check_at:
                    if not inbox.alive():
                        return
                    check_at = now + _LIVENESS_SECONDS
                if pending and now >= flush_at:
                    flush()
                try:
                    event = incoming.get(
                        timeout=min(0.1, max(0.0, check_at - now))
                    )
                except queue.Empty:
                    continue
                if event is None:
                    flush()
                    if not attached:
                        raise PairError(
                            "The notebook stream ended before attachment was confirmed."
                        )
                    reconnect = True
                    break
                if isinstance(event, Exception):
                    flush()
                    if isinstance(event, StaleNotebookError) and attached:
                        return
                    if not attached or not isinstance(
                        event,
                        (
                            PairConnectionError,
                            OSError,
                            http.client.HTTPException,
                        ),
                    ):
                        raise PairError(
                            "The agent message stream could not continue."
                        ) from event
                    reconnect = True
                    break
                if event.name == "reset":
                    attachment = None
                elif event.name == "attachment":
                    payload = json.loads(event.data)["attachment"]
                    if payload.get("identity") == config.identity:
                        attachment = payload["id"]
                        if not attached:
                            attached = True
                            ready()
                elif event.name == "ready":
                    if attachment is None:
                        raise PairError(
                            "The notebook stream did not confirm its attachment."
                        )
                    reconnect_delay = 0.1
                elif event.name == "attachment.removed":
                    if json.loads(event.data)["id"] == attachment:
                        flush()
                        return
                elif event.name == "custom":
                    payload = json.loads(event.data)["custom"]
                    if payload["type"] != AGENT_MESSAGE_TYPE:
                        if event.id is not None:
                            cursor = event.id
                        continue
                    if not attached:
                        raise PairError(
                            "The notebook stream did not confirm its attachment."
                        )
                    message = inbox_message(
                        payload["data"],
                        notebook=config.notebook,
                        budget=inbox.inbox_bytes,
                        files=files,
                    )
                    combined = (
                        f"{pending}\n\n{message}" if pending else message
                    )
                    if len(combined.encode("utf-8")) > inbox.inbox_bytes:
                        flush()
                        combined = message
                    if not pending:
                        flush_at = time.monotonic() + _BURST_SECONDS
                    pending = combined
                if event.id is not None:
                    cursor = event.id
        finally:
            stopped.set()
            for response in responses:
                response.close()
            reader.join(timeout=1)
        if reconnect:
            if not _wait_reconnect(inbox, reconnect_delay):
                return
            reconnect_delay = min(reconnect_delay * 2, _RECONNECT_MAX_SECONDS)


def main() -> None:
    record = None
    store = None
    try:
        bootstrap = msgspec.json.decode(sys.stdin.read(), type=_Bootstrap)
        config = bootstrap.config
        store = ConnectionStore(root=Path(bootstrap.root))
        record = store.load(config.identity)
        if record is None or record.forwarder != ProcessHandle.capture(
            os.getpid()
        ):
            raise PairError(
                "The agent message forwarder does not own its connection."
            )
        log_path = store.root.parent / f"forwarder-{config.identity}.log"
        handler = RotatingFileHandler(
            log_path, maxBytes=64 * 1024, backupCount=1, encoding="utf-8"
        )
        os.chmod(log_path, 0o600)
        _LOGGER.addHandler(handler)
        _LOGGER.setLevel(logging.INFO)

        def ready() -> None:
            sys.stdout.write("attached\n")
            sys.stdout.flush()

        inbox = harness_for(config.target.kind).open_inbox(config.target)
        run_forwarder(config, inbox, ready=ready)
    except (PairError, OSError, ValueError, KeyError, TypeError) as error:
        try:
            sys.stdout.write("failed\n")
            sys.stdout.flush()
        except OSError:
            pass
        # Native command output can contain tokens or agent message content.
        _LOGGER.error(
            "%s",
            str(error)
            if isinstance(error, PairError)
            else "The agent message forwarder stopped after a malformed stream or I/O error.",
        )
    finally:
        if record is not None and store is not None:
            with store.locked(record.identity):
                store.remove(record)


if __name__ == "__main__":
    main()
