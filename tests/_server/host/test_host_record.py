# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import stat
import sys
from typing import TYPE_CHECKING

import msgspec
from starlette.testclient import TestClient

from marimo._host import protocol
from marimo._server.host import record as record_module
from marimo._server.host.context import HOST_API_PATH
from marimo._server.host.lifespan import host as host_lifespan
from marimo._server.host.record import host_url
from marimo._server.main import create_starlette_app
from marimo._utils.lifespans import Lifespans
from tests._server.mocks import get_starlette_server_state_init

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_the_url_always_names_a_loopback_address() -> None:
    assert host_url("0.0.0.0", 2718, "") == (
        f"http://127.0.0.1:2718{HOST_API_PATH}"
    )
    assert host_url("::1", 2718, "/marimo") == (
        f"http://[::1]:2718/marimo{HOST_API_PATH}"
    )
    assert host_url("[::1]", 2718, "") == f"http://[::1]:2718{HOST_API_PATH}"


def test_the_lifespan_serves_the_host_while_the_server_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(
        base_url="", enable_auth=True, lifespan=Lifespans([host_lifespan])
    )
    get_starlette_server_state_init().apply(app.state)

    with TestClient(
        app, base_url="http://127.0.0.1:1234", client=("127.0.0.1", 50000)
    ) as client:
        [path] = list((tmp_path / "hosts").glob("*.json"))
        record = msgspec.json.decode(
            path.read_bytes(), type=protocol.HostRecord
        )
        assert record.url == host_url("localhost", 1234, "")
        assert record.process.pid == os.getpid()
        if sys.platform != "win32":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

        # The record's token opens the API; nothing else does.
        probe = f"{HOST_API_PATH}/notebooks/x/export?format=py"
        refused = client.get(probe)
        assert refused.status_code == 401
        admitted = client.get(
            probe, headers={"Authorization": f"Bearer {record.token}"}
        )
        assert admitted.status_code == 404

        # The workspace's one notebook is already published.
        context = app.state.host_context
        assert len(context.host.state.notebooks) == 1

    assert list((tmp_path / "hosts").glob("*.json")) == []
    assert app.state.host_context is None
