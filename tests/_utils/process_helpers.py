# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable


def wait_until(
    predicate: Callable[[], bool],
    timeout_seconds: float,
    message: str,
    *,
    poll_interval_seconds: float = 0.05,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(poll_interval_seconds)
    pytest.fail(message)


def cleanup_process(process: object) -> None:
    import psutil

    assert isinstance(process, psutil.Process)
    try:
        process.terminate()
        try:
            process.wait(timeout=2)
        except psutil.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
    except psutil.NoSuchProcess:
        pass
