# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest

from marimo._server.discovery.manager import (
    DiscoveryManager,
    build_discovery_manager,
)
from marimo._server.workspace import (
    NEW_FILE,
    DirectoryWorkspace,
    EmptyWorkspace,
)
from marimo._session.model import SessionMode
from marimo._session.types import KernelState, Session
from marimo._types.ids import SessionId
from tests._server.mocks import get_mock_session_manager

if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch

MARIMO_APP = "import marimo\napp = marimo.App()\n"


async def test_watch_retries_failed_initial_scan(
    monkeypatch: MonkeyPatch,
) -> None:
    manager = DiscoveryManager(
        session_manager=get_mock_session_manager(),
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo",
    )
    catalog = manager.catalog
    attempts = 0

    async def flaky_catalog():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporarily unavailable")
        return await catalog()

    monkeypatch.setattr(manager, "catalog", flaky_catalog)
    events = manager.watch()
    try:
        assert await asyncio.wait_for(anext(events), 0.5) == (
            "event: catalog.changed\ndata: {}\n\n"
        )
        assert await asyncio.wait_for(anext(events), 3.5) == (
            "event: catalog.changed\ndata: {}\n\n"
        )
    finally:
        await events.aclose()
        await manager.close()


async def test_watch_reconnect_during_cleanup(
    monkeypatch: MonkeyPatch,
) -> None:
    manager = DiscoveryManager(
        session_manager=get_mock_session_manager(),
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo",
    )
    scanning = asyncio.Queue[None]()
    cancelling = asyncio.Queue[None]()
    finish_cleanup = asyncio.Event()

    async def blocked_catalog():
        scanning.put_nowait(None)
        try:
            await asyncio.Future()
        finally:
            cancelling.put_nowait(None)
            await finish_cleanup.wait()

    monkeypatch.setattr(manager, "catalog", blocked_catalog)
    first = manager.watch()
    second = manager.watch()
    closing = None
    try:
        await anext(first)
        await asyncio.wait_for(scanning.get(), 2.5)
        closing = asyncio.create_task(first.aclose())
        await asyncio.wait_for(cancelling.get(), 0.5)
        await asyncio.wait_for(anext(second), 0.5)
        finish_cleanup.set()
        await asyncio.wait_for(closing, 0.5)
        await asyncio.wait_for(scanning.get(), 2.5)
        await second.aclose()
        await asyncio.wait_for(cancelling.get(), 0.5)
    finally:
        finish_cleanup.set()
        if closing is not None:
            await closing
        await first.aclose()
        await second.aclose()
        await manager.close()


@pytest.mark.parametrize("session_count", [0, 1, 2])
@pytest.mark.parametrize("directory", [False, True])
async def test_untitled_catalog_and_open_agree(
    session_count: int, directory: bool, tmp_path: Path
) -> None:
    session_manager = get_mock_session_manager()
    session_manager.workspace = (
        DirectoryWorkspace(str(tmp_path), include_markdown=False)
        if directory
        else EmptyWorkspace()
    )
    for index in range(session_count):
        session = Mock(spec=Session)
        session.app_file_manager = Mock(path=None)
        session.initialization_id = f"{NEW_FILE}{index}"
        session.kernel_state.return_value = KernelState.NOT_STARTED
        session_manager._repository.add_sync(SessionId(str(index)), session)
    manager = DiscoveryManager(
        session_manager=session_manager,
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo",
    )
    notebooks = (await manager.catalog()).projects[0].notebooks
    if directory and not session_count:
        assert notebooks == []
        return
    (notebook,) = notebooks
    assert notebook.openable == (session_count <= 1)
    if session_count > 1:
        with pytest.raises(RuntimeError, match="not openable"):
            await manager.open_notebook(notebook.id)
    else:
        response = await manager.open_notebook(notebook.id)
        query = parse_qs(urlparse(response.uri).query)
        assert query["file"] == [f"{NEW_FILE}0" if session_count else NEW_FILE]


@pytest.mark.parametrize("with_session", [False, True])
async def test_open_refreshes_deleted_notebook(
    tmp_path: Path, with_session: bool
) -> None:
    path = tmp_path / "one.py"
    path.write_text(MARIMO_APP)
    session_manager = get_mock_session_manager()
    session_manager.workspace = DirectoryWorkspace(
        str(tmp_path), include_markdown=False
    )
    if with_session:
        session = Mock(spec=Session)
        session.app_file_manager = Mock(path=str(path))
        session.initialization_id = str(path)
        session.kernel_state.return_value = KernelState.NOT_STARTED
        session_manager._repository.add_sync(SessionId("session"), session)
    manager = DiscoveryManager(
        session_manager=session_manager,
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo",
    )
    (notebook,) = (await manager.catalog()).projects[0].notebooks
    assert parse_qs(
        urlparse((await manager.open_notebook(notebook.id)).uri).query
    )["file"] == ["one.py"]
    path.unlink()
    if with_session:
        (remaining,) = (await manager.catalog()).projects[0].notebooks
        assert (remaining.id, remaining.openable) == (notebook.id, False)
        with pytest.raises(RuntimeError, match="not openable"):
            await manager.open_notebook(notebook.id)
    else:
        with pytest.raises(KeyError, match="Notebook not found"):
            await manager.open_notebook(notebook.id)


async def test_catalog_and_watch_detect_external_notebook_changes(
    tmp_path: Path,
) -> None:
    (tmp_path / "one.py").write_text(MARIMO_APP)
    session_manager = get_mock_session_manager()
    session_manager.workspace = DirectoryWorkspace(
        str(tmp_path), include_markdown=False
    )
    manager = DiscoveryManager(
        session_manager=session_manager,
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo",
    )
    catalog = await manager.catalog()
    assert [item.path for item in catalog.projects[0].notebooks] == ["one.py"]

    (tmp_path / "two.py").write_text(MARIMO_APP)
    catalog = await manager.catalog()
    assert [item.path for item in catalog.projects[0].notebooks] == [
        "one.py",
        "two.py",
    ]

    events = manager.watch()
    try:
        await anext(events)
        (tmp_path / "three.py").write_text(MARIMO_APP)
        assert await asyncio.wait_for(anext(events), timeout=2.5) == (
            "event: catalog.changed\ndata: {}\n\n"
        )
        catalog = await manager.catalog()
        assert [item.path for item in catalog.projects[0].notebooks] == [
            "one.py",
            "three.py",
            "two.py",
        ]
        # An initial scan could explain the first notification, but not this one.
        (tmp_path / "three.py").unlink()
        assert await asyncio.wait_for(anext(events), timeout=2.5) == (
            "event: catalog.changed\ndata: {}\n\n"
        )
        catalog = await manager.catalog()
        assert [item.path for item in catalog.projects[0].notebooks] == [
            "one.py",
            "two.py",
        ]
    finally:
        await events.aclose()


@pytest.mark.parametrize(
    ("kind", "name"),
    [
        (None, None),
        ("marimo", "Research server"),
        ("custom-editor", "My editor"),
    ],
)
def test_build_manager_uses_actual_loopback_and_environment(
    monkeypatch: MonkeyPatch, kind: str | None, name: str | None
) -> None:
    for key, value in [
        ("MARIMO_DISCOVERY_KIND", kind),
        ("MARIMO_DISCOVERY_NAME", name),
    ]:
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    manager = build_discovery_manager(
        session_manager=get_mock_session_manager(),
        host="0.0.0.0",
        port=9876,
        base_url="/notebooks",
    )
    assert manager is not None
    assert manager.record.url == (
        "http://127.0.0.1:9876/notebooks/api/marimo/v1"
    )
    assert (manager.record.kind, manager.record.name) == (
        kind or "marimo",
        name or "marimo CLI",
    )


@pytest.mark.parametrize(
    ("host", "advertised_host"),
    [
        ("localhost", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("0.0.0.0", "127.0.0.1"),
        ("::ffff:127.0.0.1", "127.0.0.1"),
        ("::1", "[::1]"),
        ("[::1]", "[::1]"),
        ("::", "[::1]"),
    ],
)
def test_build_manager_advertises_reachable_loopback(
    host: str, advertised_host: str
) -> None:
    manager = build_discovery_manager(
        session_manager=get_mock_session_manager(),
        host=host,
        port=2718,
        base_url="/notebooks",
    )
    assert manager is not None
    assert manager.record.url == (
        f"http://{advertised_host}:2718/notebooks/api/marimo/v1"
    )


@pytest.mark.parametrize(
    "host",
    [
        "192.168.1.20",
        "example.com",
        "127.0.0.2",
        "127.1.2.3",
        "::ffff:127.0.0.2",
    ],
)
def test_build_manager_rejects_unrepresentable_bind(host: str) -> None:
    assert (
        build_discovery_manager(
            session_manager=get_mock_session_manager(),
            host=host,
            port=2718,
            base_url="",
        )
        is None
    )


def test_build_manager_disabled_for_run_and_opt_out(
    monkeypatch: MonkeyPatch,
) -> None:
    assert (
        build_discovery_manager(
            session_manager=get_mock_session_manager(mode=SessionMode.RUN),
            host="127.0.0.1",
            port=2718,
            base_url="",
        )
        is None
    )
    monkeypatch.setenv("MARIMO_DISCOVERY_ENABLED", "0")
    assert (
        build_discovery_manager(
            session_manager=get_mock_session_manager(),
            host="127.0.0.1",
            port=2718,
            base_url="",
        )
        is None
    )
