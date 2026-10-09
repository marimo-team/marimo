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
from dataclasses import asdict, dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

import msgspec

from marimo._cli.pair.artifacts import HandoffFiles, inbox_message
from marimo._cli.pair.client import (
    EventStream,
    PairConnectionError,
    PairError,
    SSEEvent,
    StaleSessionError,
    iter_sse,
    open_events,
)
from marimo._cli.pair.connection import Connection, ConnectionStore
from marimo._cli.pair.delivery import DeliveryTarget, ProcessHandle
from marimo._cli.pair.harnesses import adapter_for
from marimo._utils.subprocess import kill_subprocess

if TYPE_CHECKING:
    from collections.abc import Callable

    from marimo._cli.pair.delivery import HarnessAdapter

_LOGGER = logging.getLogger(__name__)
_LIVENESS_SECONDS = 15.0
_BURST_SECONDS = 1.0
_RECONNECT_MAX_SECONDS = 5.0


@dataclass(frozen=True)
class ForwarderConfig:
    url: str
    session: str
    attachment: str
    token: str | None
    target: DeliveryTarget


class _Bootstrap(msgspec.Struct):
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

    assert config.target.process is not None
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
            1,
            config.attachment,
            config.session,
            config.target.kind,
            config.target.process.pid,
            config.target.process.started,
            handle.pid,
            handle.started,
            time.time(),
        )
        store.save(record)
        assert process.stdin is not None
        assert process.stdout is not None
        output = process.stdout
        # Secrets travel through the private pipe, never argv or a state file.
        process.stdin.write(
            json.dumps(
                {"config": asdict(config), "root": str(store.root)}
            ).encode("utf-8")
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
                "The handoff forwarder did not attach within 10 seconds."
            ) from error
        if line != b"attached\n" or process.poll() is not None:
            raise PairError(
                "The handoff forwarder could not attach. Check the server, token and preview flag."
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
) -> None:
    def put(item: SSEEvent | Exception | None) -> None:
        while not stopped.is_set():
            try:
                incoming.put(item, timeout=0.1)
                return
            except queue.Full:
                continue

    try:
        response = open_events(
            url=config.url,
            session=config.session,
            token=config.token,
            attachment=config.attachment,
            name=config.target.label,
        )
        responses.append(response)
        try:
            if stopped.is_set():
                return
            for event in iter_sse(response):
                if stopped.is_set():
                    return
                put(event)
        finally:
            response.close()
    except (
        PairError,
        OSError,
        http.client.HTTPException,
        ValueError,
    ) as error:
        put(error)
    else:
        put(None)


def _wait_reconnect(
    adapter: HarnessAdapter, target: DeliveryTarget, delay: float
) -> bool:
    deadline = time.monotonic() + delay
    while adapter.alive(target):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(remaining, 0.1))
    return False


def run_forwarder(
    config: ForwarderConfig,
    adapter: HarnessAdapter,
    *,
    ready: Callable[[], None],
) -> None:
    files = HandoffFiles()
    files.cleanup()
    pending = ""
    flush_at = 0.0
    check_at = time.monotonic()
    attached = False
    reconnect_delay = 0.1

    def flush() -> None:
        nonlocal pending
        if pending:
            adapter.send(config.target, pending)
            pending = ""

    while adapter.alive(config.target):
        incoming: queue.Queue[SSEEvent | Exception | None] = queue.Queue(
            maxsize=64
        )
        stopped = threading.Event()
        responses: list[EventStream] = []
        reader = threading.Thread(
            target=_read_stream,
            args=(config, incoming, stopped, responses),
            daemon=True,
        )
        reader.start()
        reconnect = False
        try:
            while True:
                now = time.monotonic()
                if now >= check_at:
                    if not adapter.alive(config.target):
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
                    return
                if isinstance(event, Exception):
                    flush()
                    if isinstance(event, StaleSessionError) and attached:
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
                            "The handoff stream could not continue."
                        ) from event
                    reconnect = True
                    break
                if event.name == "attached":
                    payload = json.loads(event.data)
                    if (
                        not isinstance(payload, dict)
                        or payload.get("id") != config.attachment
                    ):
                        raise PairError(
                            "The handoff stream returned a different attachment."
                        )
                    reconnect_delay = 0.1
                    if not attached:
                        attached = True
                        ready()
                elif event.name == "handoff":
                    if not attached:
                        raise PairError(
                            "The handoff stream did not confirm its attachment."
                        )
                    message = inbox_message(
                        json.loads(event.data),
                        session=config.session,
                        budget=adapter.inbox_bytes,
                        files=files,
                    )
                    combined = (
                        f"{pending}\n\n{message}" if pending else message
                    )
                    if len(combined.encode("utf-8")) > adapter.inbox_bytes:
                        flush()
                        combined = message
                    if not pending:
                        flush_at = time.monotonic() + _BURST_SECONDS
                    pending = combined
        finally:
            stopped.set()
            for response in responses:
                response.close()
            reader.join(timeout=1)
        if reconnect:
            if not _wait_reconnect(adapter, config.target, reconnect_delay):
                return
            reconnect_delay = min(reconnect_delay * 2, _RECONNECT_MAX_SECONDS)


def main() -> None:
    record = None
    store = None
    try:
        bootstrap = msgspec.json.decode(sys.stdin.read(), type=_Bootstrap)
        config = bootstrap.config
        store = ConnectionStore(root=Path(bootstrap.root))
        record = store.load(config.attachment)
        if record is None or record.forwarder != ProcessHandle.capture(
            os.getpid()
        ):
            raise PairError(
                "The handoff forwarder does not own its connection."
            )
        log_path = store.root.parent / f"forwarder-{config.attachment}.log"
        handler = RotatingFileHandler(
            log_path, maxBytes=64 * 1024, backupCount=1, encoding="utf-8"
        )
        os.chmod(log_path, 0o600)
        _LOGGER.addHandler(handler)
        _LOGGER.setLevel(logging.INFO)

        def ready() -> None:
            sys.stdout.write("attached\n")
            sys.stdout.flush()

        run_forwarder(config, adapter_for(config.target.kind), ready=ready)
    except (PairError, OSError, ValueError, KeyError, TypeError) as error:
        try:
            sys.stdout.write("failed\n")
            sys.stdout.flush()
        except OSError:
            pass
        # Native command output can contain tokens or handoff content.
        _LOGGER.error(
            "%s",
            str(error)
            if isinstance(error, PairError)
            else "The handoff forwarder stopped after a malformed stream or I/O error.",
        )
    finally:
        if record is not None and store is not None:
            with store.locked(record.attachment_id):
                store.remove(record)


if __name__ == "__main__":
    main()
