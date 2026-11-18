# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from contextlib import closing
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
import websockets.sync.client

from marimo._cli.pair.client import open_events, resolve_host
from tests._cli._pair_server import _wait_for_kernel_ready, pair_test_server
from tests._cli.test_pair_integration import _run

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests._cli._pair_server import PairTestServer


def wait_values(path: Path, predicate: Callable[[list], bool]) -> list:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        values = [json.loads(line) for line in path.read_text().splitlines()]
        if predicate(values):
            return values
        time.sleep(0.02)
    raise AssertionError(f"Missing updates: {path.read_text()}")


_created_cells: dict[str, set[str]] = {}


def run_cell(server: PairTestServer, cell_id: str, code: str) -> None:
    """Put the cell in the document and run it through the host."""
    created = _created_cells.setdefault(server.notebook_id, set())
    base = f"{server.url}/api/marimo/v1/notebooks/{server.notebook_id}"

    def post(path: str, body: object) -> None:
        request = urllib.request.Request(
            f"{base}{path}",
            data=json.dumps(body).encode(),
            headers={
                **server._headers,
                "Content-Type": "application/json",
                "Idempotency-Key": uuid4().hex,
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status in (200, 202)

    post(
        "/edits",
        {
            "changes": [
                {
                    "kind": "put_cell",
                    "base_etag": "*" if cell_id in created else None,
                    "cell": {"id": cell_id, "code": code},
                }
            ]
        },
    )
    created.add(cell_id)
    post("/runtime/runs", {"cells": [{"id": cell_id}]})


def agent_stream(
    server: PairTestServer,
    name: str,
    *,
    identity: str = "same-agent",
    messaging: bool = True,
):
    host = resolve_host(server.url)
    return closing(
        open_events(
            url=host.url,
            notebook=server.notebook_id,
            token=host.token,
            identity=identity,
            name=name,
            messaging=messaging,
        )
    )


@pytest.mark.parametrize("ipc", [False, True])
def test_consumer_subscription_busy_kernel_and_session_replacement(
    tmp_path: Path, ipc: bool
) -> None:
    if ipc:
        (tmp_path / "pyproject.toml").write_text(
            f"[tool.marimo.venv]\npath = {json.dumps(sys.prefix)}\nwritable = false\n"
        )
    updates = tmp_path / "updates.jsonl"
    updates.touch()
    busy = tmp_path / "busy"
    release = tmp_path / "release"
    with pair_test_server(tmp_path, token="private-token") as server:
        code = f"""
import marimo as mo
import json
from pathlib import Path
from types import SimpleNamespace
from marimo._runtime.context import get_context
_consumer = SimpleNamespace(agent_connected=False)
def _changed(agents, consumer=_consumer):
    import json
    from pathlib import Path
    from marimo._runtime.context import get_context
    consumer.agent_connected = bool(agents)
    with open({str(updates)!r}, "a") as out:
        out.write(json.dumps([[(a.id, a.name) for a in agents], get_context().cell_id, consumer.agent_connected, Path({str(busy)!r}).exists()]) + "\\n")
_unsubscribe = mo.agents.subscribe_connections(_changed)
with open({str(updates)!r}, "a") as out:
    out.write(json.dumps("returned") + "\\n")
"""
        run_cell(server, "observe", code)
        first = wait_values(updates, lambda values: len(values) == 2)
        assert first == ["returned", [[], None, False, False]]
        run_cell(
            server,
            "busy",
            f"""
import time as _time
from pathlib import Path as _Path
_Path({str(busy)!r}).touch()
while not _Path({str(release)!r}).exists():
    _time.sleep(0.01)
_Path({str(busy)!r}).unlink()
""",
        )
        deadline = time.monotonic() + 5
        while not busy.exists():
            assert time.monotonic() < deadline
            time.sleep(0.02)
        with agent_stream(server, "Old"):
            with agent_stream(server, "New"):
                assert updates.read_text().count("\n") == 2
                release.touch()
                values = wait_values(
                    updates,
                    lambda values: values[-1][0] == [["same-agent", "New"]],
                )
                assert 3 <= len(values) <= 4
                assert all(
                    value[1:] == [None, True, False] for value in values[2:]
                )
            wait_values(
                updates,
                lambda values: values[-1][0] == [["same-agent", "Old"]],
            )
        disconnected = wait_values(updates, lambda values: values[-1][0] == [])
        assert disconnected[-1] == [[], None, False, False]
        run_cell(server, "observe", "print('registration cell reran')")
        with agent_stream(server, "After rerun"):
            wait_values(
                updates,
                lambda values: (
                    values[-1][0] == [["same-agent", "After rerun"]]
                ),
            )
        wait_values(updates, lambda values: values[-1][0] == [])

        request = urllib.request.Request(
            f"{server.url}/api/kernel/restart_session",
            data=b"{}",
            headers={
                **server._headers,
                "Content-Type": "application/json",
                "Marimo-Session-Id": server.session_id,
            },
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
        url = server.url.replace("http://", "ws://", 1)
        with websockets.sync.client.connect(
            f"{url}/ws?session_id={server.session_id}",
            additional_headers=server._headers,
        ) as replacement:
            assert _wait_for_kernel_ready(replacement) == server.notebook_id
            request = urllib.request.Request(
                f"{server.url}/api/sessions", headers=server._headers
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                sessions = json.load(response)
            assert (
                sessions[server.session_id]["session_id"]
                != server.stable_session_id
            )
            request = urllib.request.Request(
                f"{server.url}/api/pair/notebooks/{server.stable_session_id}/agents/subscriptions",
                data=json.dumps({"subscription_id": "a" * 32}).encode(),
                headers={
                    **server._headers,
                    "Content-Type": "application/json",
                },
            )
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request, timeout=5)
            assert error.value.code == 404
            fresh = tmp_path / "fresh.json"
            run_cell(
                server,
                "fresh",
                f"""
import marimo as _mo
def _fresh_changed(agents):
    from pathlib import Path
    Path({str(fresh)!r}).write_text(str(len(agents)))
_fresh_unsubscribe = _mo.agents.subscribe_connections(_fresh_changed)
""",
            )
            deadline = time.monotonic() + 5
            while not fresh.exists():
                assert time.monotonic() < deadline
                time.sleep(0.02)
            assert fresh.read_text() == "0"


def test_subscription_timeout_from_cell(tmp_path: Path) -> None:
    from tests._http import http_test_server

    result = tmp_path / "timeout.jsonl"
    result.touch()
    with http_test_server() as endpoint, pair_test_server(tmp_path) as server:
        endpoint.delay = 4
        run_cell(
            server,
            "timeout",
            f"""
import marimo as mo
import time
import json
from dataclasses import replace
from marimo._runtime.context import get_context
_kernel = get_context()._kernel
_original = _kernel.agent_messaging
_kernel.agent_messaging = replace(_original, url={endpoint.url!r})
_start = time.monotonic()
try:
    mo.agents.subscribe_connections(lambda agents: None)
except mo.agents.AgentError as _error:
    with open({str(result)!r}, "a") as _out:
        _out.write(json.dumps([str(_error), time.monotonic() - _start]) + "\\n")
finally:
    _kernel.agent_messaging = _original
""",
        )
        values = wait_values(result, bool)
        assert "timed out" in values[0][0]
        assert values[0][1] < 1.8


@pytest.mark.parametrize("cleanup", ["unsubscribe", "delete"])
def test_listing_and_subscription_cleanup(
    tmp_path: Path, cleanup: str
) -> None:
    from contextlib import ExitStack

    updates = tmp_path / "listing.jsonl"
    updates.touch()
    stop = tmp_path / "stop"
    with pair_test_server(tmp_path) as server, ExitStack() as stack:

        def attach(identity: str, name: str, *, messaging: bool = True):
            return stack.enter_context(
                agent_stream(
                    server, name, identity=identity, messaging=messaging
                )
            )

        attach("observer", "Cannot receive", messaging=False)
        attach("z", "First")
        attach("a", "Second")
        run_cell(
            server,
            "listing",
            f"""
import marimo as mo
import json
from pathlib import Path
_holder = []

def _changed(agents, holder=_holder):
    import json
    from pathlib import Path
    import marimo as mo
    with open({str(updates)!r}, "a") as _out:
        _out.write(json.dumps([[(a.id, a.name) for a in agents], [(a.id, a.name) for a in mo.agents.list()]]) + "\\n")
    if Path({str(stop)!r}).exists():
        holder[0]()
        holder[0]()
_holder.append(mo.agents.subscribe_connections(_changed))
""",
        )
        values = wait_values(updates, bool)
        assert values == [[[["z", "First"], ["a", "Second"]]] * 2]
        if cleanup == "unsubscribe":
            stop.touch()
            attach("z", "Newest")
            values = wait_values(updates, lambda values: len(values) == 2)
            assert values[-1] == [[["z", "Newest"], ["a", "Second"]]] * 2
        else:
            request = urllib.request.Request(
                f"{server.url}/api/marimo/v1/notebooks/{server.notebook_id}/edits",
                data=json.dumps(
                    {
                        "changes": [
                            {
                                "kind": "delete_cell",
                                "id": "listing",
                                "base_etag": "*",
                            }
                        ]
                    }
                ).encode(),
                headers={
                    **server._headers,
                    "Content-Type": "application/json",
                    "Idempotency-Key": uuid4().hex,
                },
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                assert response.status == 200
            attach("z", "After deletion")
            values = wait_values(updates, lambda values: len(values) == 2)
            assert (
                values[-1] == [[["z", "After deletion"], ["a", "Second"]]] * 2
            )
            stop.touch()
            attach("z", "Stop")
            wait_values(updates, lambda values: len(values) == 3)
        result = _run(server, "-c", "print('cleanup barrier')")
        assert result.returncode == 0, result.stderr + result.stdout
        before = updates.read_text()
        attach("b", "After cleanup")
        result = _run(server, "-c", "print('event barrier')")
        assert result.returncode == 0, result.stderr + result.stdout
        assert updates.read_text() == before


def test_registration_without_cell_and_callback_error_isolation(
    tmp_path: Path,
) -> None:
    updates = tmp_path / "nested.jsonl"
    updates.touch()
    with pair_test_server(tmp_path) as server:
        run_cell(
            server,
            "register",
            f"""
import marimo as mo
from types import SimpleNamespace
_consumer = SimpleNamespace(subscribed=False, unsubscribe=None)
def _healthy(agents):
    import json
    from marimo._runtime.context import get_context
    with open({str(updates)!r}, "a") as out:
        out.write(json.dumps([[(a.id, a.name) for a in agents], get_context().cell_id]) + "\\n")
def _broken(agents, consumer=_consumer, healthy=_healthy):
    import marimo as mo
    if not consumer.subscribed:
        consumer.subscribed = True
        consumer.unsubscribe = mo.agents.subscribe_connections(healthy)
    raise ValueError("consumer callback failed")
_unsubscribe = mo.agents.subscribe_connections(_broken)
""",
        )
        assert wait_values(updates, bool) == [[[], None]]
        with agent_stream(server, "Agent"):
            wait_values(updates, lambda values: len(values) == 2)
        assert wait_values(updates, lambda values: len(values) == 3) == [
            [[], None],
            [[["same-agent", "Agent"]], None],
            [[], None],
        ]


def test_unsubscribe_makes_queued_update_harmless(tmp_path: Path) -> None:
    updates = tmp_path / "queued.jsonl"
    updates.touch()
    busy = tmp_path / "busy"
    release = tmp_path / "release"
    done = tmp_path / "done"
    with pair_test_server(tmp_path) as server:
        run_cell(
            server,
            "subscribe",
            f"""
import marimo as mo
from types import SimpleNamespace
consumer = SimpleNamespace(unsubscribe=None)
def _changed(agents):
    import json
    with open({str(updates)!r}, "a") as out:
        out.write(json.dumps([(a.id, a.name) for a in agents]) + "\\n")
consumer.unsubscribe = mo.agents.subscribe_connections(_changed)
""",
        )
        assert wait_values(updates, bool) == [[]]
        run_cell(
            server,
            "busy",
            f"""
import time as _time
from pathlib import Path as _Path
_Path({str(busy)!r}).touch()
while not _Path({str(release)!r}).exists():
    _time.sleep(0.01)
consumer.unsubscribe()
consumer.unsubscribe()
_Path({str(done)!r}).touch()
""",
        )
        deadline = time.monotonic() + 5
        while not busy.exists():
            assert time.monotonic() < deadline
            time.sleep(0.02)
        with agent_stream(server, "Queued"):
            release.touch()
            deadline = time.monotonic() + 5
            while not done.exists():
                assert time.monotonic() < deadline
                time.sleep(0.02)
            result = _run(server, "-c", "print('queue barrier')")
            assert result.returncode == 0, result.stderr + result.stdout
            assert updates.read_text() == "[]\n"
