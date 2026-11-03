# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import threading
from collections import deque
from queue import Queue
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from marimo._messaging.cell_output import CellChannel
from marimo._messaging.console_output_worker import ConsoleMsg
from marimo._messaging.context import execution_id_context, run_id_context
from marimo._messaging.streams import (
    ThreadSafeStderr,
    ThreadSafeStdout,
    ThreadSafeStream,
    Watcher,
    redirect,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(params=[ThreadSafeStdout, ThreadSafeStderr])
def capture(
    request: pytest.FixtureRequest,
) -> Iterator[tuple[ThreadSafeStream, ThreadSafeStdout | ThreadSafeStderr]]:
    stream = ThreadSafeStream(Mock(), Queue[str](), redirect_console=False)
    stream.console_msg_cv = threading.Condition()
    stream.console_msg_queue = deque()
    output = request.param(stream, forward_os_streams=False)
    fd = os.open(os.devnull, os.O_WRONLY)
    output._original_fd = fd
    output._watcher = Watcher(output)
    try:
        yield stream, output
    finally:
        output._stop()
        os.close(fd)


def test_pause_waits_for_inflight_output(
    capture: tuple[ThreadSafeStream, ThreadSafeStdout | ThreadSafeStderr],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream, output = capture
    entered = threading.Event()
    release = threading.Event()
    exiting = threading.Event()
    finished = threading.Event()
    errors: list[BaseException] = []
    write = output.write

    def delayed_write(data: str) -> int:
        entered.set()
        assert release.wait(timeout=5)
        return write(data)

    monkeypatch.setattr(output, "write", delayed_write)

    def execute() -> None:
        try:
            with run_id_context("run"), execution_id_context("cell", "exec"):
                stream.cell_id = CellId_t("cell")
                try:
                    with redirect(output):
                        os.write(output._original_fd, b"hello")
                        assert entered.wait(timeout=5)
                        exiting.set()
                finally:
                    stream.cell_id = None
        except BaseException as exc:
            errors.append(exc)
        finally:
            finished.set()

    execution = threading.Thread(target=execute)
    execution.start()
    try:
        assert exiting.wait(timeout=5)
        assert not finished.wait(timeout=0.1)
    finally:
        release.set()
        execution.join(timeout=5)
    assert not execution.is_alive()
    assert errors == []
    assert list(stream.console_msg_queue) == [
        ConsoleMsg(
            stream=(
                CellChannel.STDOUT
                if isinstance(output, ThreadSafeStdout)
                else CellChannel.STDERR
            ),
            cell_id=CellId_t("cell"),
            data="hello",
            mimetype="text/plain",
            run_id="run",
            execution_id="exec",
        )
    ]


def test_pause_drains_without_waiting_for_inherited_writer(
    capture: tuple[ThreadSafeStream, ThreadSafeStdout | ThreadSafeStderr],
) -> None:
    stream, output = capture
    stream.cell_id = CellId_t("cell")
    inherited_fd: int | None = None
    text = "x" * 1023 + "€" + "y" * 1024
    try:
        with redirect(output):
            inherited_fd = os.dup(output._original_fd)
            os.write(inherited_fd, text.encode())
        stream.cell_id = None
        messages = list(stream.console_msg_queue)
        assert all(isinstance(msg, ConsoleMsg) for msg in messages)
        assert (
            "".join(
                msg.data for msg in messages if isinstance(msg, ConsoleMsg)
            )
            == text
        )
    finally:
        if inherited_fd is not None:
            os.close(inherited_fd)


def test_output_after_pause_keeps_last_execution_identity(
    capture: tuple[ThreadSafeStream, ThreadSafeStdout | ThreadSafeStderr],
) -> None:
    stream, output = capture
    with run_id_context("run"), execution_id_context("cell", "exec"):
        stream.cell_id = CellId_t("cell")
        with redirect(output):
            pass
    stream.cell_id = None
    watcher = output._watcher
    assert isinstance(watcher, Watcher)
    os.write(watcher.write_fd, b"late")
    with stream.console_msg_cv:
        assert stream.console_msg_cv.wait_for(
            lambda: bool(stream.console_msg_queue), timeout=5
        )
    assert list(stream.console_msg_queue) == [
        ConsoleMsg(
            stream=(
                CellChannel.STDOUT
                if isinstance(output, ThreadSafeStdout)
                else CellChannel.STDERR
            ),
            cell_id=CellId_t("cell"),
            data="late",
            mimetype="text/plain",
            run_id="run",
            execution_id="exec",
        )
    ]


def test_reader_failure_is_reported_after_restoring_descriptor(
    capture: tuple[ThreadSafeStream, ThreadSafeStdout | ThreadSafeStderr],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream, output = capture
    failed = threading.Event()

    def fail_write(_data: str) -> int:
        failed.set()
        raise ValueError("reader failure")

    monkeypatch.setattr(output, "write", fail_write)
    stream.cell_id = CellId_t("cell")

    def execute() -> None:
        with redirect(output):
            os.write(output._original_fd, b"hello")
            assert failed.wait(timeout=5)

    with pytest.raises(RuntimeError, match="OS stream reader failed"):
        execute()
    assert os.fstat(output._original_fd) == os.stat(os.devnull)
    with pytest.raises(RuntimeError, match="OS stream reader failed"):
        with redirect(output):
            pytest.fail("A failed reader must not be restarted")


def test_interrupted_execution_still_drains_and_restores_descriptor(
    capture: tuple[ThreadSafeStream, ThreadSafeStdout | ThreadSafeStderr],
) -> None:
    stream, output = capture
    stream.cell_id = CellId_t("cell")

    def execute() -> None:
        with redirect(output):
            os.write(output._original_fd, b"before interrupt")
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        execute()
    stream.cell_id = None
    assert os.fstat(output._original_fd) == os.stat(os.devnull)
    assert (
        "".join(
            msg.data
            for msg in stream.console_msg_queue
            if isinstance(msg, ConsoleMsg)
        )
        == "before interrupt"
    )
