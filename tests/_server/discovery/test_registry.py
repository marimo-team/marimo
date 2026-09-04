# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import stat
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from inline_snapshot import snapshot

from marimo._server.api.lifespans import discovery
from marimo._server.discovery.manager import DiscoveryManager
from marimo._server.discovery.models import InstanceRecord
from marimo._server.discovery.registry import DiscoveryRegistryWriter
from marimo._server.main import create_starlette_app
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission assertions")
def test_registry_is_private_and_round_trips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "marimo._server.discovery.registry.marimo_state_dir",
        lambda: tmp_path,
    )
    record = InstanceRecord(
        id=UUID("e250b117-6e0e-48af-a5cd-7c1fd5e14a67"),
        kind="marimo",
        name="marimo CLI",
        pid=123,
        started_at=datetime(2026, 9, 3, 15, 4, 5, tzinfo=timezone.utc),
        url="http://127.0.0.1:2718/api/marimo/v1",
        token="secret",
    )
    writer = DiscoveryRegistryWriter(record)

    writer.register()

    discovery = tmp_path / "discovery"
    version = discovery / "v1"
    record_path = version / f"{record.id}.json"
    assert stat.S_IMODE(discovery.stat().st_mode) == 0o700
    assert stat.S_IMODE(version.stat().st_mode) == 0o700
    assert stat.S_IMODE(record_path.stat().st_mode) == 0o600
    assert json.loads(record_path.read_text()) == snapshot(
        {
            "id": "e250b117-6e0e-48af-a5cd-7c1fd5e14a67",
            "kind": "marimo",
            "name": "marimo CLI",
            "pid": 123,
            "started_at": "2026-09-03T15:04:05Z",
            "url": "http://127.0.0.1:2718/api/marimo/v1",
            "token": "secret",
        }
    )

    writer.deregister()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission assertions")
def test_registry_rejects_unsafe_existing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "marimo._server.discovery.registry.marimo_state_dir",
        lambda: tmp_path,
    )
    discovery = tmp_path / "discovery"
    discovery.mkdir(mode=0o755)
    os.chmod(discovery, 0o755)
    record = InstanceRecord(
        id=uuid4(),
        kind="marimo",
        name="marimo CLI",
        pid=123,
        started_at=datetime.now(timezone.utc),
        url="http://127.0.0.1:2718/api/marimo/v1",
        token="secret",
    )

    with pytest.raises(PermissionError, match="accessible to other users"):
        DiscoveryRegistryWriter(record).register()

    assert stat.S_IMODE(discovery.stat().st_mode) == 0o755


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission assertions")
async def test_discovery_record_follows_server_lifespan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "marimo._server.discovery.registry.marimo_state_dir",
        lambda: tmp_path,
    )
    session_manager = get_mock_session_manager()
    manager = DiscoveryManager(
        session_manager=session_manager,
        browser_url="http://127.0.0.1:2718",
        kind="marimo",
        name="marimo CLI",
    )
    app = create_starlette_app(base_url="", enable_auth=True)
    replace(
        get_starlette_server_state_init(session_manager=session_manager),
        discovery_manager=manager,
    ).apply(app.state)
    record_path = tmp_path / "discovery" / "v1" / f"{manager.instance_id}.json"

    async with discovery(app):
        assert record_path.is_file()

    assert not record_path.exists()
