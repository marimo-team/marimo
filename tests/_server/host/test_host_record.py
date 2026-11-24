# Copyright 2026 Marimo. All rights reserved.
"""Host discovery records and server lifecycle."""

from __future__ import annotations

import asyncio
import os
import signal
import stat
import subprocess
import sys
from contextlib import ExitStack
from threading import Thread
from typing import TYPE_CHECKING

import msgspec
import pytest
import uvicorn

from marimo._core import backend as be, protocol
from marimo._server.host import HOST_API_PATH, record as record_module
from marimo._server.host.lifespan import host as host_lifespan
from marimo._server.host.record import host_url
from marimo._server.main import create_starlette_app
from marimo._session.model import SessionMode
from marimo._utils.lifespans import Lifespans
from tests._core.conftest import (
    ScriptedBackend,
    add_notebook,
    project,
    record,
    runtime_id_of,
)
from tests._server.host.drive import finished
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("host", "loopback"),
    [
        ("0.0.0.0", "127.0.0.1"),
        ("127.0.0.1", "127.0.0.1"),
        ("127.1.2.3", "127.1.2.3"),
        ("localhost", "127.0.0.1"),
        ("LOCALHOST", "127.0.0.1"),
        ("::ffff:127.0.0.1", "127.0.0.1"),
        ("::1", "[::1]"),
        ("[::1]", "[::1]"),
        ("::", "[::1]"),
        ("[::]", "[::1]"),
    ],
)
def test_the_url_names_the_loopback_that_reaches_the_bind(
    host: str, loopback: str
) -> None:
    assert host_url(host, 2718, "/marimo") == (
        f"http://{loopback}:2718/marimo{HOST_API_PATH}"
    )


@pytest.mark.parametrize("host", ["192.168.1.5", "10.0.0.1", "fe80::1", "x"])
def test_an_unreachable_bind_has_no_url(host: str) -> None:
    assert host_url(host, 2718, "") is None


async def test_an_unreachable_bind_writes_no_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(
        base_url="", enable_auth=True, lifespan=Lifespans([host_lifespan])
    )
    state = get_starlette_server_state_init()
    state.apply(app.state)
    app.state.server = uvicorn.Server(
        uvicorn.Config(app, host="192.168.1.5", port=1234)
    )

    async with app.router.lifespan_context(app):
        assert list((tmp_path / "hosts-v1").glob("*.json")) == []
        assert app.state.host_context is not None


async def test_run_mode_writes_no_record_and_serves_no_host_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(
        base_url="", enable_auth=False, lifespan=Lifespans([host_lifespan])
    )
    get_starlette_server_state_init(
        session_manager=get_mock_session_manager(mode=SessionMode.RUN)
    ).apply(app.state)
    app.state.server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=1234)
    )

    async with app.router.lifespan_context(app):
        assert not (tmp_path / "hosts-v1").exists()
        assert (await finished(app, "GET", "/notebooks")).status == 404


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


async def test_idle_host_expires_results_and_stops_maintenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    app.state.server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=1234)
    )
    async with host_lifespan(app):
        context = app.state.host_context
        host = context.bridge.host
        now = 0.0
        host.clock = context.mutations.clock = lambda: now
        host.update_project(project())
        notebook = await add_notebook(
            host,
            msgspec.structs.replace(record(), operations=("runtime.execute",)),
            ScriptedBackend(),
        )
        notebook.adopt(lambda _: None)
        notebook.observe(be.Running(runtime_id_of(notebook)))
        headers = {
            "Authorization": f"Bearer {context.token}",
            "Idempotency-Key": "run",
        }
        response = await finished(
            app,
            "POST",
            f"/notebooks/{notebook.id}/runtime/execute",
            headers=headers,
            body=b'{"code":"42"}',
        )
        assert response.status == 202
        run_id = protocol.RunId(response.json()["id"])
        eid = protocol.ExecutionId("execution")
        notebook.observe(
            be.Planned(run_id, (be.PlannedExecution(eid, None, "hash"),))
        )
        notebook.observe(be.Completed(eid, protocol.SucceededOutcome()))
        notebook.observe(be.Done(run_id, "succeeded"))
        removed = asyncio.Event()
        host.subscribe(
            lambda event: (
                removed.set()
                if isinstance(event.event, protocol.RunRemovedEvent)
                else None
            ),
            notebook_id=notebook.id,
        )
        [maintenance] = [
            task
            for task in asyncio.all_tasks()
            if task.get_name() == "host.retention"
        ]
        now = 300
        await asyncio.wait_for(removed.wait(), timeout=5)
        assert context.mutations.replies == {}
    assert maintenance.done()
    assert app.state.host_context is None


@pytest.mark.parametrize("legacy", [False, True])
def test_discovery_reads_the_live_record_without_exposing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, legacy: bool
) -> None:
    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    if legacy:
        monkeypatch.setattr(
            record_module, "_lock_local_record", lambda _: None
        )
    writer = record_module.HostRecordFile(
        url="http://127.0.0.1:2718/base/api/marimo/v1", token="private-token"
    )
    writer.write()
    try:
        if legacy or os.name == "nt":
            [path] = (tmp_path / "hosts-v1").iterdir()
            assert not path.name.startswith(record_module._LOCKED_PREFIX)
        assert list(record_module.discover_hosts()) == [writer._record]
        writer.remove()
        assert list(record_module.discover_hosts()) == []
    finally:
        writer.remove()


@pytest.mark.skipif(os.name != "posix", reason="POSIX lifetime locks")
def test_next_publisher_prunes_only_the_crashed_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    if not record_module._supports_local_locks(tmp_path.stat().st_dev):
        pytest.skip("test directory does not support local record locks")
    directory = record_module.marimo_state_dir() / "hosts-v1"
    url = "http://127.0.0.1:2718/api/marimo/v1"
    pending: list[Thread] = []
    monkeypatch.setattr(Thread, "start", lambda worker: pending.append(worker))
    with ExitStack() as cleanup:
        live = record_module.HostRecordFile(url=url, token="live")
        live.write()
        cleanup.callback(live.remove)
        pending.pop().run()
        [live_path] = directory.iterdir()

        child = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import os, signal, sys\n"
                    "from marimo._server.host.record import HostRecordFile\n"
                    "HostRecordFile(url=sys.argv[1], token='crashed').write()\n"
                    "os.kill(os.getpid(), signal.SIGKILL)"
                ),
                url,
            ],
            timeout=15,
        )
        assert child.returncode == -signal.SIGKILL
        [crashed] = set(directory.iterdir()) - {live_path}
        legacy = directory / "legacy.json"
        legacy.write_bytes(crashed.read_bytes())
        legacy.chmod(0o600)
        invalid = directory / f"{record_module._LOCKED_PREFIX}{'0' * 32}.json"
        invalid.write_bytes(b"{}")
        invalid.chmod(0o600)
        public = directory / f"{record_module._LOCKED_PREFIX}{'1' * 32}.json"
        public.write_bytes(crashed.read_bytes())
        public.chmod(0o644)

        new = record_module.HostRecordFile(url=url, token="new")
        new.write()
        cleanup.callback(new.remove)
        [worker] = pending
        assert worker.daemon
        assert crashed.exists()
        worker.run()
        assert set(directory.iterdir()) == {
            live_path,
            new._path,
            legacy,
            invalid,
            public,
        }
        assert {r.token for r in record_module.discover_hosts()} == {
            "live",
            "new",
        }


@pytest.mark.skipif(sys.platform != "linux", reason="Linux mount table")
def test_lock_scope_follows_the_device_of_the_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from unittest.mock import mock_open

    mounts = (
        "10 1 8:1 / / rw - ext4 /dev/sda1 rw\n"
        "11 10 0:42 / /home rw - nfs4 server:/home rw,local_lock=all\n"
    )
    monkeypatch.setattr("builtins.open", mock_open(read_data=mounts.encode()))
    assert record_module._supports_local_locks(os.makedev(8, 1))
    assert not record_module._supports_local_locks(os.makedev(0, 42))


@pytest.mark.skipif(os.name != "posix", reason="POSIX discovery validation")
@pytest.mark.parametrize(
    "invalid",
    [
        "directory",
        "file",
        "symlink",
        "remote",
        "credentials",
        "stale",
        "large",
        "version",
    ],
)
def test_discovery_skips_untrusted_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    import json

    monkeypatch.setattr(record_module, "marimo_state_dir", lambda: tmp_path)
    writer = record_module.HostRecordFile(
        url="http://127.0.0.1:2718/api/marimo/v1", token="private-token"
    )
    writer.write()
    path = writer._path
    assert path is not None
    data = json.loads(path.read_bytes())
    if invalid == "directory":
        path.parent.chmod(0o755)
    elif invalid == "file":
        path.chmod(0o644)
    elif invalid == "symlink":
        target = path.with_suffix(".private")
        path.rename(target)
        path.symlink_to(target)
    elif invalid == "large":
        path.write_bytes(b" " * 65537)
    else:
        if invalid == "remote":
            data["url"] = "http://example.com/api/marimo/v1"
        elif invalid == "credentials":
            data["url"] = "http://user@127.0.0.1:2718/api/marimo/v1"
        elif invalid == "stale":
            data["process"]["started_at"] = "2000-01-01T00:00:00Z"
        else:
            data["version"] = 2
        path.write_text(json.dumps(data))
    try:
        assert list(record_module.discover_hosts()) == []
        assert path.exists()
    finally:
        writer.remove()
