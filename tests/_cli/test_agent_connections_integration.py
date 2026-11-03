# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

import pytest
import websockets.sync.client

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


def run_cell(server: PairTestServer, cell_id: str, code: str) -> None:
    request = urllib.request.Request(
        f"{server.url}/api/kernel/run",
        data=json.dumps({"cellIds": [cell_id], "codes": [code]}).encode(),
        headers={
            **server._headers,
            "Content-Type": "application/json",
            "Marimo-Session-Id": server.session_id,
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        assert response.status == 200


def agent_stream(server: PairTestServer, name: str):
    url = server.url.replace("http://", "ws://", 1)
    return websockets.sync.client.connect(
        f"{url}/api/marimo/v1/notebooks/{server.notebook_id}/events/ws",
        additional_headers={
            **server._headers,
            "Marimo-Attachment-Kind": "agent",
            "Marimo-Attachment-Identity": "same-agent",
            "Marimo-Attachment-Name": name,
        },
    )


@pytest.mark.requires("anywidget")
@pytest.mark.parametrize("ipc", [False, True])
def test_observation_widget_busy_kernel_and_rerun(
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
    with pair_test_server(
        tmp_path, token="private-token", skew_protection=True
    ) as server:
        code = f"""
import marimo as mo
import anywidget
import traitlets
import json
from pathlib import Path
from marimo._runtime.context import get_context
class _Widget(anywidget.AnyWidget):
    agent_connected = traitlets.Bool(False).tag(sync=True)
_widget = _Widget()
def _changed(agents):
    _widget.set_trait("agent_connected", bool(agents))
    with open({str(updates)!r}, "a") as out:
        out.write(json.dumps([[(a.id, a.name) for a in agents], get_context().cell_id, _widget.agent_connected, Path({str(busy)!r}).exists()]) + "\\n")
_unsubscribe = mo.agents.subscribe_connections(_changed)
with open({str(updates)!r}, "a") as out:
    out.write(json.dumps("returned") + "\\n")
"""
        run_cell(server, "observe", code)
        first = wait_values(updates, lambda values: len(values) == 2)
        assert first == ["returned", [[], "observe", False, False]]
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
                    value[1:] == ["observe", True, False]
                    for value in values[2:]
                )
                # Check the existing model stream, as an external widget uses it.
                deadline = time.monotonic() + 5
                while True:
                    frame = json.loads(
                        server._websocket.recv(
                            timeout=max(0.1, deadline - time.monotonic())
                        )
                    )
                    if frame["event"] != "marimo":
                        continue
                    notification = frame["data"]["marimo"]
                    if (
                        notification["op"] == "model-lifecycle"
                        and notification["message"]
                        .get("state", {})
                        .get("agent_connected")
                        is True
                    ):
                        break
                    assert time.monotonic() < deadline
            wait_values(
                updates,
                lambda values: values[-1][0] == [["same-agent", "Old"]],
            )
        disconnected = wait_values(updates, lambda values: values[-1][0] == [])
        assert disconnected[-1] == [[], "observe", False, False]
        run_cell(server, "observe", "print('observer removed')")
        # A scratch command is a barrier after the cell rerun and its cleanup.
        result = _run(server, "-c", "print('ready')")
        assert result.returncode == 0, result.stderr + result.stdout
        before = updates.read_text()
        with agent_stream(server, "After rerun"):
            result = _run(server, "-c", "print('barrier')")
            assert result.returncode == 0, result.stderr + result.stdout
        assert updates.read_text() == before

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
