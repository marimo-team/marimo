import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Callable

import pytest

from marimo._types.lifespan import Lifespan
from marimo._utils.lifespans import Lifespans


class MockApp:
    def __init__(self) -> None:
        self.setup_calls: list[str] = []
        self.teardown_calls: list[str] = []


def create_mock_lifespan() -> Callable[[str], Lifespan[MockApp]]:
    def mock_lifespan(name: str) -> Lifespan[MockApp]:
        @asynccontextmanager
        async def lifespan(app: MockApp) -> AsyncIterator[None]:
            app.setup_calls.append(name)
            try:
                yield
            finally:
                app.teardown_calls.append(name)

        return lifespan

    return mock_lifespan


async def test_empty_lifespans() -> None:
    app = MockApp()
    lifespans: Lifespans[MockApp] = Lifespans([])
    assert not lifespans.has_lifespans()

    async with lifespans(app):
        assert len(app.setup_calls) == 0
        assert len(app.teardown_calls) == 0


async def test_single_lifespan() -> None:
    app = MockApp()
    mock_lifespan = create_mock_lifespan()
    lifespans: Lifespans[MockApp] = Lifespans([mock_lifespan("test1")])
    assert lifespans.has_lifespans()

    async with lifespans(app):
        assert app.setup_calls == ["test1"]
        assert len(app.teardown_calls) == 0

    assert app.setup_calls == ["test1"]
    assert app.teardown_calls == ["test1"]


async def test_multiple_lifespans() -> None:
    app = MockApp()
    mock_lifespan = create_mock_lifespan()
    lifespans: Lifespans[MockApp] = Lifespans(
        [
            mock_lifespan("test1"),
            mock_lifespan("test2"),
            mock_lifespan("test3"),
        ]
    )
    assert lifespans.has_lifespans()

    async with lifespans(app):
        assert app.setup_calls == ["test1", "test2", "test3"]
        assert len(app.teardown_calls) == 0

    assert app.setup_calls == ["test1", "test2", "test3"]
    assert app.teardown_calls == [
        "test3",
        "test2",
        "test1",
    ]  # Teardown in reverse order


async def test_lifespan_error_handling() -> None:
    app = MockApp()
    mock_lifespan = create_mock_lifespan()

    def failing_lifespan(name: str) -> Lifespan[MockApp]:
        @asynccontextmanager
        async def lifespan(app: MockApp) -> AsyncIterator[None]:
            app.setup_calls.append(name)
            try:
                yield
            finally:
                app.teardown_calls.append(name)
                raise ValueError(f"Error in {name}")

        return lifespan

    lifespans: Lifespans[MockApp] = Lifespans(
        [
            mock_lifespan("test1"),
            failing_lifespan("test2"),
            mock_lifespan("test3"),
        ]
    )

    with pytest.raises(ValueError, match="Error in test2"):
        async with lifespans(app):
            pass

    # Even with errors, setup and teardown should be called in correct order
    assert app.setup_calls == ["test1", "test2", "test3"]
    assert app.teardown_calls == ["test3", "test2", "test1"]


async def test_lifespan_cancellation() -> None:
    app = MockApp()
    mock_lifespan = create_mock_lifespan()
    lifespans: Lifespans[MockApp] = Lifespans(
        [mock_lifespan("test1"), mock_lifespan("test2")]
    )

    async with lifespans(app):
        assert app.setup_calls == ["test1", "test2"]
        # Simulate cancellation
        raise asyncio.CancelledError()

    # Teardown should still be called even on cancellation
    assert app.teardown_calls == ["test2", "test1"]
