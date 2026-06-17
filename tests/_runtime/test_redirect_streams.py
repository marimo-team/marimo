# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import time

from marimo._runtime.redirect_streams import redirect_streams
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._types.ids import CellId_t
from tests._runtime._helpers.streams import MockStderr, MockStdin, MockStdout
from tests.conftest import _MockStream


def test_nested_from_scratch_swaps_cell_id() -> None:
    """When code_mode runs cells from the scratchpad, the inner cell's
    console output must be tagged with its own cell_id, not __scratch__."""
    stream = _MockStream()
    inner_id = CellId_t("real_cell")

    with redirect_streams(SCRATCH_CELL_ID, stream, None, None, None):
        with redirect_streams(inner_id, stream, None, None, None):
            assert stream.cell_id == inner_id
        assert stream.cell_id == SCRATCH_CELL_ID


def test_os_stdout_uses_active_cell_id_with_context_streams() -> None:
    stream = _MockStream()
    stdout = MockStdout(stream)
    stdout._original_fd = 1
    stdout._watcher.fd = 1
    stderr = MockStderr(stream)
    stdin = MockStdin(stream)

    with redirect_streams(CellId_t("cell"), stream, stdout, stderr, stdin):
        os.system("echo redirected stdout")

    deadline = time.monotonic() + 1
    while "redirected stdout\n" not in "".join(stdout.messages):
        assert time.monotonic() < deadline
        time.sleep(0.01)


def test_os_stderr_uses_active_cell_id_with_context_streams() -> None:
    stream = _MockStream()
    stdout = MockStdout(stream)
    stderr = MockStderr(stream)
    stderr._original_fd = 2
    stderr._watcher.fd = 2
    stdin = MockStdin(stream)

    with redirect_streams(CellId_t("cell"), stream, stdout, stderr, stdin):
        os.system("echo redirected stderr >&2")

    deadline = time.monotonic() + 1
    while "redirected stderr\n" not in "".join(stderr.messages):
        assert time.monotonic() < deadline
        time.sleep(0.01)
