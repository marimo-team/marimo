# Copyright 2026 Marimo. All rights reserved.
"""Lifespans contributed through the `marimo.kernel.lifespan` registry."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import pytest

from marimo._runtime.commands import (
    CreateNotebookCommand,
    UpdateUIElementCommand,
)
from marimo._runtime.runtime import _KERNEL_LIFESPAN_REGISTRY
from tests._runtime._helpers.session import mocked_kernel_session

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


@pytest.fixture
def lifespan_events() -> Iterator[list[str]]:
    """Register a kernel lifespan that logs each enter and exit."""
    events: list[str] = []

    @contextlib.asynccontextmanager
    async def recorder(_app: None) -> AsyncIterator[None]:
        events.append("enter")
        try:
            yield
        finally:
            events.append("exit")

    _KERNEL_LIFESPAN_REGISTRY.register("recorder", recorder)
    try:
        yield events
    finally:
        _KERNEL_LIFESPAN_REGISTRY.unregister("recorder")


def test_kernel_torn_down_before_instantiate_skips_lifespan(
    lifespan_events: list[str],
) -> None:
    with mocked_kernel_session():
        pass

    assert lifespan_events == []


async def test_kernel_enters_and_exits_lifespan_once(
    lifespan_events: list[str],
) -> None:
    no_ui_values = UpdateUIElementCommand.from_ids_and_values([])
    request = CreateNotebookCommand(
        execution_requests=(),
        cell_ids=(),
        set_ui_element_value_request=no_ui_values,
        auto_run=True,
    )
    # The session exits inside this test's running event loop.
    with mocked_kernel_session() as tk:
        await tk.kernel.instantiate(request)
        await tk.kernel.instantiate(request)
        assert lifespan_events == ["enter"]

    assert lifespan_events == ["enter", "exit"]
