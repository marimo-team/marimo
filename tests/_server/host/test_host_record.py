# Copyright 2026 Marimo. All rights reserved.
"""Host discovery records and server lifecycle."""

from __future__ import annotations

import os
import stat
import sys
from typing import TYPE_CHECKING

import msgspec
import pytest
import uvicorn

from marimo._core import protocol
from marimo._server.host import HOST_API_PATH, record as record_module
from marimo._server.host.lifespan import host as host_lifespan
from marimo._server.host.record import host_url
from marimo._server.main import create_starlette_app
from marimo._utils.lifespans import Lifespans
from tests._server.host.drive import finished
from tests._server.mocks import get_starlette_server_state_init

if TYPE_CHECKING:
    from pathlib import Path


def test_the_url_always_names_a_loopback_address() -> None:
    assert (
        host_url("0.0.0.0", 2718, "")
        == f"http://127.0.0.1:2718{HOST_API_PATH}"
    )
    assert host_url("::1", 2718, "/marimo") == (
        f"http://[::1]:2718/marimo{HOST_API_PATH}"
    )
    assert host_url("[::1]", 2718, "") == f"http://[::1]:2718{HOST_API_PATH}"


@pytest.mark.parametrize("external_port", [1234, 8443])
async def test_the_lifespan_serves_the_host_while_the_server_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, external_port: int
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(
        base_url="", enable_auth=True, lifespan=Lifespans([host_lifespan])
    )
    state = get_starlette_server_state_init()
    state.apply(app.state)
    app.state.port = external_port
    app.state.host = "proxy.example" if external_port != 1234 else "localhost"
    app.state.server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=1234)
    )

    async with app.router.lifespan_context(app):
        [path] = list((tmp_path / "hosts-v1").glob("*.json"))
        record = msgspec.json.decode(
            path.read_bytes(), type=protocol.HostRecord
        )
        assert record.url == f"http://127.0.0.1:1234{HOST_API_PATH}"
        assert record.process.pid == os.getpid()
        if sys.platform != "win32":
            assert stat.S_IMODE(path.stat().st_mode) == 0o600
            assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

        probe = "/notebooks/x/runtime"
        refused = await finished(
            app, "DELETE", probe, headers={"Idempotency-Key": "k"}
        )
        assert refused.status == 401
        admitted = await finished(
            app,
            "DELETE",
            probe,
            headers={
                "Authorization": f"Bearer {record.token}",
                "Idempotency-Key": "k",
            },
        )
        assert admitted.status == 404

    assert list((tmp_path / "hosts-v1").glob("*.json")) == []
