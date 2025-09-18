# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import time
from typing import Any
from unittest.mock import patch

import pytest

from marimo._plugins.stateless.status._progress import (
    _Progress,
    progress_bar,
    spinner,
)
from marimo._runtime.context.types import runtime_context_installed


# Test initialization
def test_progress_init() -> None:
    progress = _Progress(
        title="Test",
        subtitle="Running",
        total=100,
        show_rate=True,
        show_eta=True,
    )
    assert progress.title == "Test"
    assert progress.subtitle == "Running"
    assert progress.total == 100
    assert progress.current == 0
    assert progress.closed is False
    assert progress.loading_spinner is False
    assert progress.show_rate is True
    assert progress.show_eta is True
    # sleep 10ms
    time.sleep(0.01)
    rate = progress._get_rate()
    assert rate == 0.0
    eta = progress._get_eta()
    assert eta is None


# Test update_progress method
@patch("marimo._runtime.output._output.flush")
def test_update_progress(mock_flush: Any) -> None:
    progress = _Progress(
        title="Test",
        subtitle="Running",
        total=10000000,
        show_rate=True,
        show_eta=True,
    )
    # sleep 100ms
    time.sleep(0.1)
    progress.update_progress(
        increment=10, title="Updated", subtitle="Still Running"
    )
    assert progress.current == 10
    assert progress.title == "Updated"
    assert progress.subtitle == "Still Running"
    rate = progress._get_rate()
    assert rate is not None
    assert rate > 0.0
    eta = progress._get_eta()
    assert eta is not None
    assert eta > 0.0
    mock_flush.assert_called_once()


# Test update_progress without arguments
@patch("marimo._runtime.output._output.flush")
def test_update_progress_no_args(mock_flush: Any) -> None:
    del mock_flush
    progress = _Progress(
        title="Test",
        subtitle="Running",
        total=100,
        show_rate=False,
        show_eta=False,
    )
    # sleep 100ms
    time.sleep(0.1)
    progress.update_progress()
    assert progress.current == 1
    assert progress.title == "Test"
    assert progress.subtitle == "Running"
    rate = progress._get_rate()
    assert rate is None
    eta = progress._get_eta()
    assert eta is None


# Test update_progress with closed progress
@patch("marimo._runtime.output._output.flush")
def test_update_progress_closed(mock_flush: Any) -> None:
    progress = _Progress(
        title="Test",
        subtitle="Running",
        total=100,
        show_rate=True,
        show_eta=True,
    )
    progress.close()
    assert progress.closed is True
    with pytest.raises(RuntimeError):
        progress.update_progress()
    mock_flush.assert_called_once()


def test_spinner_without_context():
    assert runtime_context_installed() is False

    with spinner("Test"):
        assert True

    with spinner(subtitle="Loading data ...") as _spinner:
        assert spinner
        _spinner.update(subtitle="Crunching numbers ...")


def test_progress_without_context():
    assert runtime_context_installed() is False

    for i in progress_bar(range(10)):
        assert i is not None

    with progress_bar(total=10) as bar:
        for _ in range(10):
            assert bar
            bar.update()

    # iterator (no len()) with total
    assert progress_bar(iter(range(1000)), total=1000)

    with pytest.raises(RuntimeError):
        for _ in progress_bar(total=10):
            pass


async def sleep(seconds):
    import asyncio

    tasks = [asyncio.create_task(asyncio.sleep(s, s)) for s in seconds]
    for future in asyncio.as_completed(tasks):
        yield await future


async def test_progress_async():
    assert runtime_context_installed() is False

    ait = sleep([0.01, 0.003, 0.001])
    result = [s async for s in progress_bar(ait, total=3)]
    assert result == [0.001, 0.003, 0.01]


def test_progress_no_total_error():
    assert runtime_context_installed() is False

    def sync_generator():
        yield 1
        yield 2
        yield 3

    with pytest.raises(
        TypeError,
        match="Cannot determine the length of a collection. A `total` must be provided.",
    ):
        progress_bar(sync_generator())


def test_progress_async_no_total_error():
    assert runtime_context_installed() is False

    async def async_generator():
        yield 1
        yield 2
        yield 3

    with pytest.raises(
        TypeError,
        match="Cannot determine the length of a collection. A `total` must be provided.",
    ):
        progress_bar(async_generator())


def test_progress_for_loop_error():
    assert runtime_context_installed() is False

    async def async_generator():
        yield 1

    with pytest.raises(
        RuntimeError,
        match="Cannot iterate over an async collection with `for`. Use `async for` instead.",
    ):
        for _ in progress_bar(async_generator(), total=1):
            pass


async def test_progress_async_for_loop_error():
    assert runtime_context_installed() is False

    with pytest.raises(
        RuntimeError,
        match="Cannot iterate over a sync collection with `async for`. Use `for` instead.",
    ):
        async for _ in progress_bar([1, 2, 3]):
            pass


async def test_progress_async_for_loop_without_collection_error():
    assert runtime_context_installed() is False

    with pytest.raises(
        RuntimeError,
        match="progress_bar can only be iterated over if a collection is provided",
    ):
        async for _ in progress_bar(total=1):
            pass
