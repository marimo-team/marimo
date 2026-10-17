# Copyright 2026 Marimo. All rights reserved.
"""Host API authorization, event streams, and commands."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlsplit

import msgspec
import pytest
from starlette.routing import Route

from marimo._core import backend as be, protocol
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.protocol import ProjectMessage
from marimo._core.run_log import RetentionPolicy
from marimo._server.host import api as api_module
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.host.index import WorkspaceIndex
from marimo._server.main import create_starlette_app
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import FixedFilesWorkspace, SingleFileWorkspace
from marimo._session.notebook import AppFileManager
from tests._core.conftest import ScriptedBackend, make_notebook, runtime_id_of
from tests._server.host.drive import (
    PORT,
    Response,
    finished,
    request,
    until_ready,
    wait_for,
)
from tests._server.mocks import (
    get_mock_session_manager,
    get_starlette_server_state_init,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.applications import Starlette

TOKEN = "record-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


async def analyzed(notebook: Notebook) -> protocol.Analysis:
    """Wait for the notebook's analysis, which runs off the event loop."""
    deadline = asyncio.get_running_loop().time() + 5
    while notebook.analysis is None:
        if asyncio.get_running_loop().time() > deadline:
            raise TimeoutError("the notebook was not analyzed")
        await asyncio.sleep(0.01)
    return notebook.analysis


def key(value: str) -> dict[str, str]:
    return {**AUTH, "Idempotency-Key": value}


class Harness:
    def __init__(
        self, app: Starlette, bridge: SessionBridge, root: Path
    ) -> None:
        self.app = app
        self.bridge = bridge
        self.root = root
        self.now = 0.0
        self.host.clock = lambda: self.now
        self.backends: dict[str, ScriptedBackend] = {}

    @property
    def host(self) -> Host:
        return self.bridge.host

    @property
    def notebook_id(self) -> str:
        (notebook,) = [
            n for n in self.host.notebooks.values() if n.path == "forecasts.py"
        ]
        return notebook.id

    def backend(self) -> ScriptedBackend:
        return self.backends[self.notebook_id]

    async def running(self) -> str:
        """Start a runtime and simulate the backend's running update."""
        response = await finished(
            self.app,
            "PUT",
            f"/notebooks/{self.notebook_id}/runtime",
            headers=key("start"),
            body=b"{}",
        )
        assert response.status == 202, response.body
        (await self.host.notebook(self.notebook_id)).observe(
            be.Running(
                runtime_id_of(await self.host.notebook(self.notebook_id)),
                "0.25.0",
            )
        )
        return self.notebook_id


@pytest.fixture
def harness(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> Harness:
    (tmp_path / "forecasts.py").write_text(
        "import marimo\napp = marimo.App()\n"
    )
    workspace = FixedFilesWorkspace(
        [MarimoFile(name="forecasts.py", path=str(tmp_path / "forecasts.py"))],
        directory=str(tmp_path),
    )
    app = create_starlette_app(base_url="", enable_auth=True)
    manager = get_mock_session_manager()
    get_starlette_server_state_init(session_manager=manager).apply(app.state)
    bridge = SessionBridge(manager)
    bridge.host.retention = getattr(request, "param", RetentionPolicy())
    harness = Harness(app, bridge, tmp_path)

    def make(notebook_id: str) -> ScriptedBackend:
        backend = ScriptedBackend()
        harness.backends[notebook_id] = backend
        return backend

    monkeypatch.setattr(bridge, "_make_backend", make)
    bridge.index = WorkspaceIndex(
        bridge.host, workspace, bridge._initialize_notebook
    )
    bridge.index.refresh()
    app.state.host_context = HostContext(
        bridge=bridge,
        token=TOKEN,
        port=PORT,
        receipt_seconds=30,
        clock=lambda: harness.now,
    )
    return harness


async def test_the_token_the_address_and_the_name_are_all_checked(
    harness: Harness,
) -> None:
    app = harness.app
    assert (await finished(app, "GET", "/events")).status == 401
    assert (
        await finished(
            app, "GET", "/events", headers={"Authorization": "Bearer nope"}
        )
    ).status == 401
    assert (
        await finished(
            app, "GET", "/events", headers=AUTH, client=("10.0.0.5", 1)
        )
    ).status == 403
    assert (
        await finished(
            app, "GET", "/events", headers=AUTH, host="evil.example:1234"
        )
    ).status == 403
    assert (
        await finished(
            app, "GET", "/events", headers=AUTH, host="127.0.0.1:9999"
        )
    ).status == 403
    app.state.host_context = None
    refused = await finished(app, "GET", "/events", headers=AUTH)
    assert refused.status == 404
    assert refused.json()["type"].endswith("/not-found")


async def test_unknown_routes_are_problems(harness: Harness) -> None:
    response = await finished(harness.app, "GET", "/nothing", headers=AUTH)
    assert response.status == 404
    assert response.headers["content-type"] == "application/problem+json"


async def test_a_wrong_method_on_a_known_route_is_a_405_problem(
    harness: Harness,
) -> None:
    response = await finished(harness.app, "GET", "/notebooks", headers=AUTH)
    assert response.status == 405
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"].endswith("/method-not-allowed")
    assert "POST" in response.headers["allow"]


def _declared_routes() -> dict[str, set[str]]:
    methods: dict[str, set[str]] = {}
    for route in api_module.build_app().routes:
        assert isinstance(route, Route)
        path = route.path.replace("{id}", "nb-x").replace("{run_id}", "run-x")
        methods.setdefault(path, set()).update(route.methods or set())
    return methods


_DECLARED = _declared_routes()
_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
_UNKNOWN = [
    "/nothing",
    "/notebooks/nb-x/nothing",
    "/events/",
    "/notebooks/",
    "/notebooks/nb-x/runtime/runs/run-x/",
]
_SWEEP = [
    (path, method) for path in [*_DECLARED, *_UNKNOWN] for method in _METHODS
]


@pytest.mark.parametrize(("path", "method"), _SWEEP)
async def test_every_method_on_every_route_is_a_response_not_a_500(
    harness: Harness, path: str, method: str
) -> None:
    response, _, disconnect = request(harness.app, method, path, headers=AUTH)
    await wait_for(response, lambda r: r.status != 0)
    disconnect()
    assert response.status != 500
    if not 200 <= response.status < 300:
        assert response.headers["content-type"] == "application/problem+json"
    if response.status == 405:
        allowed = {m.strip() for m in response.headers["allow"].split(",")}
        assert allowed == _DECLARED[path]


@pytest.mark.parametrize(
    ("host", "status"),
    [
        ("127.attacker.example:1234", 403),
        ("127.1.2.3:1234", 202),
        ("localhost:1234", 202),
        ("LOCALHOST:1234", 202),
        ("[::1]:1234", 202),
        ("[::ffff:127.0.0.1]:1234", 202),
        ("[::1]junk:1234", 403),
        ("[::1", 403),
        ("[::1:1234", 403),
        ("127.0.0.1:" + "1" * 5000, 403),
    ],
)
async def test_only_loopback_names_are_admitted(
    harness: Harness, host: str, status: int
) -> None:
    response = await finished(
        harness.app,
        "PUT",
        f"/notebooks/{harness.notebook_id}/runtime",
        headers=key("start"),
        body=b"{}",
        host=host,
    )
    assert response.status == status


@pytest.mark.parametrize(
    "port",
    ["\xb2", "1234\xb2", "\xb9\xb2\xb3"],
)
def test_latin1_superscripts_are_not_a_port(port: str) -> None:
    from marimo._server.host.middleware import _host_header_ok

    assert port.isdigit()
    assert _host_header_ok(f"127.0.0.1:{port}", PORT) is False


@pytest.mark.parametrize(
    ("authorization", "status"),
    [
        ("Bearer \xe9", 401),
        ("Bearer", 401),
        ("Bearer ", 401),
        ("Basic record-token", 401),
        ("bearer  record-token ", 202),
    ],
)
async def test_malformed_bearers_are_401_problems(
    harness: Harness, authorization: str, status: int
) -> None:
    response = await finished(
        harness.app,
        "PUT",
        f"/notebooks/{harness.notebook_id}/runtime",
        headers={"Authorization": authorization, "Idempotency-Key": "start"},
        body=b"{}",
    )
    assert response.status == status
    if status != 202:
        assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize("cursor", ["x", "-1", "1" * 5000, "1 "])
async def test_a_malformed_cursor_is_a_400_problem(
    harness: Harness, cursor: str
) -> None:
    response = await finished(
        harness.app,
        "GET",
        "/events",
        headers={**AUTH, "Last-Event-ID": cursor},
    )
    assert response.status == 400
    assert response.json()["type"].endswith("/invalid-request")


async def test_a_nul_byte_in_a_path_is_a_400_problem(harness: Harness) -> None:
    response = await finished(
        harness.app,
        "POST",
        "/notebooks",
        headers=key("nul"),
        body=json.dumps(
            {
                "project_id": harness.bridge.index.project_id,
                "path": "a\u0000b.py",
            }
        ).encode(),
    )
    assert response.status == 400
    assert response.json()["type"].endswith("/invalid-request")


async def test_a_401_names_the_bearer_scheme(harness: Harness) -> None:
    response = await finished(harness.app, "GET", "/events")
    assert response.status == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/events", "/notebooks/{id}/events"])
@pytest.mark.parametrize("types", ["bogus", "notebook,bogus", "Notebook"])
async def test_an_unknown_type_filter_is_a_400_problem(
    harness: Harness, path: str, types: str
) -> None:
    response = await finished(
        harness.app,
        "GET",
        path.replace("{id}", harness.notebook_id),
        headers=AUTH,
        query=f"types={types}",
    )
    assert response.status == 400
    assert "bogus" in response.json()["detail"] or types == "Notebook"


async def test_an_empty_update_is_a_400_problem(harness: Harness) -> None:
    response = await finished(
        harness.app,
        "PATCH",
        f"/notebooks/{harness.notebook_id}",
        headers=key("empty"),
        body=b"{}",
    )
    assert response.status == 400
    assert response.json()["type"].endswith("/invalid-request")


async def test_head_on_a_stream_is_a_405_and_attaches_nothing(
    harness: Harness,
) -> None:
    notebook = await harness.host.notebook(harness.notebook_id)
    before = len(notebook._attachments)
    response = await finished(
        harness.app, "HEAD", f"/notebooks/{notebook.id}/events", headers=AUTH
    )
    assert response.status == 405
    assert response.headers["allow"] == "GET"
    assert len(notebook._attachments) == before


async def test_a_failure_inside_a_stream_does_not_restart_the_response(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_event: object) -> bytes:
        raise RuntimeError("frame failed")

    monkeypatch.setattr(api_module, "_frame", broken)
    response, task, _ = request(harness.app, "GET", "/events", headers=AUTH)
    # Older Starlette raises the body's error inside an ExceptionGroup.
    with pytest.raises(Exception) as caught:
        await asyncio.wait_for(task, 5)
    assert "frame failed" in repr(caught.value)
    assert response.status == 200
    assert response.body == b""


async def test_the_catalog_stream_sends_a_snapshot_then_changes(
    harness: Harness,
) -> None:
    response, _, disconnect = request(
        harness.app, "GET", "/events", headers=AUTH
    )
    await wait_for(response, until_ready)
    assert response.names() == ["host", "project", "notebook", "ready"]
    assert "id" not in response.records[0]
    cursor = int(response.records[-1]["id"])

    notebook = await harness.host.notebook(harness.notebook_id)
    notebook.start()
    await wait_for(response, lambda r: r.names()[-1] == "runtime")
    live = response.records[-1]
    assert int(live["id"]) > cursor
    assert live["data"]["runtime"]["status"] == "starting"
    assert "time" in live["data"]
    disconnect()


async def test_catalog_refresh_delivers_updates_on_the_event_loop(
    harness: Harness,
) -> None:
    first, first_task, disconnect_first = request(
        harness.app, "GET", "/events", headers=AUTH
    )
    await wait_for(first, until_ready)
    threads: list[int] = []
    unsubscribe = harness.host.subscribe(
        lambda _: threads.append(threading.get_ident())
    )
    new_file = harness.root / "new.py"
    new_file.write_text("import marimo\n")
    harness.bridge.index._workspace = FixedFilesWorkspace(
        [
            MarimoFile(
                name="forecasts.py", path=str(harness.root / "forecasts.py")
            ),
            MarimoFile(name="new.py", path=str(new_file)),
        ],
        directory=str(harness.root),
    )
    second, second_task, disconnect_second = request(
        harness.app, "GET", "/events", headers=AUTH
    )
    try:
        await wait_for(second, until_ready)
        await wait_for(
            first,
            lambda response: any(
                r.get("data", {}).get("notebook", {}).get("path") == "new.py"
                for r in response.records
            ),
        )
        assert threads
        assert set(threads) == {threading.get_ident()}
    finally:
        unsubscribe()
        disconnect_first()
        disconnect_second()
        await asyncio.gather(first_task, second_task)


async def test_types_and_cursors_apply_to_the_stream(harness: Harness) -> None:
    first, _, disconnect = request(
        harness.app, "GET", "/events", headers=AUTH, query="types=notebook"
    )
    await wait_for(first, until_ready)
    assert first.names() == ["notebook", "ready"]
    cursor = first.records[-1]["id"]
    disconnect()

    (await harness.host.notebook(harness.notebook_id)).start()
    resumed, _, disconnect = request(
        harness.app,
        "GET",
        "/events",
        headers={**AUTH, "Last-Event-ID": cursor},
    )
    await wait_for(resumed, until_ready)
    assert resumed.names() == ["runtime", "ready"]
    disconnect()

    bad = await finished(
        harness.app, "GET", "/events", headers={**AUTH, "Last-Event-ID": "x"}
    )
    assert bad.status == 400


async def test_a_notebook_stream_attaches_the_client(harness: Harness) -> None:
    notebook = await harness.host.notebook(harness.notebook_id)
    await analyzed(notebook)
    response, task, disconnect = request(
        harness.app, "GET", f"/notebooks/{notebook.id}/events", headers=AUTH
    )
    await wait_for(response, until_ready)
    # An empty notebook loads with marimo's one default cell.
    assert response.names() == [
        "notebook",
        "cell",
        "document",
        "analysis",
        "attachment",
        "ready",
    ]
    assert response.records[2]["data"]["document"]["order"] == [
        response.records[1]["data"]["cell"]["id"]
    ]
    assert response.records[4]["data"]["attachment"]["kind"] == "client"

    disconnect()
    await asyncio.wait_for(task, 5)
    assert [e.name for e in harness.host.events(notebook_id=notebook.id)] == [
        "notebook",
        "cell",
        "document",
        "analysis",
        "ready",
    ]

    missing = await finished(
        harness.app, "GET", "/notebooks/nope/events", headers=AUTH
    )
    assert missing.status == 404


IDENTIFIED = {
    **AUTH,
    api_module.ATTACHMENT_IDENTITY: "k1",
    api_module.ATTACHMENT_KIND: "agent",
    api_module.ATTACHMENT_NAME: "Codex",
}


async def attachment_of(
    harness: Harness, headers: dict[str, str]
) -> protocol.Attachment:
    """Open a notebook stream with `headers` and return its attachment."""
    response, task, disconnect = request(
        harness.app,
        "GET",
        f"/notebooks/{harness.notebook_id}/events",
        headers=headers,
        query="types=attachment",
    )
    await wait_for(response, until_ready)
    assert response.names() == ["attachment", "ready"]
    message = msgspec.convert(
        response.records[0]["data"], protocol.AttachmentMessage
    )
    disconnect()
    await asyncio.wait_for(task, 5)
    return message.attachment


async def test_attachment_headers_name_the_client(harness: Harness) -> None:
    attachment = await attachment_of(harness, IDENTIFIED)
    assert attachment.identity == "k1"
    assert attachment.kind == "agent"
    assert attachment.name == "Codex"


async def test_an_empty_attachment_name_is_null(harness: Harness) -> None:
    attachment = await attachment_of(
        harness, {**AUTH, api_module.ATTACHMENT_NAME: ""}
    )
    assert attachment.name is None


async def test_a_reconnect_with_one_identity_attaches_fresh(
    harness: Harness,
) -> None:
    path = f"/notebooks/{harness.notebook_id}/events"
    first, first_task, disconnect_first = request(
        harness.app, "GET", path, headers=IDENTIFIED, query="types=attachment"
    )
    await wait_for(first, until_ready)
    cursor = first.records[-1]["id"]
    old = first.records[0]["data"]["attachment"]
    disconnect_first()
    await asyncio.wait_for(first_task, 5)
    assert "attachment" not in [e.name for e in harness.host.events()]

    second, second_task, disconnect_second = request(
        harness.app,
        "GET",
        path,
        headers={**IDENTIFIED, "Last-Event-ID": cursor},
        query="types=attachment",
    )
    await wait_for(second, until_ready)
    assert second.names() == ["attachment.removed", "attachment", "ready"]
    assert second.records[0]["data"]["id"] == old["id"]
    new = second.records[1]["data"]["attachment"]
    assert new["identity"] == old["identity"] == "k1"
    assert new["id"] != old["id"]

    disconnect_second()
    await asyncio.wait_for(second_task, 5)


async def test_custom_events_use_their_own_sse_kind(
    harness: Harness,
) -> None:
    notebook = await harness.host.notebook(harness.notebook_id)
    path = f"/notebooks/{notebook.id}/events"
    custom, custom_task, disconnect_custom = request(
        harness.app, "GET", path, headers=AUTH, query="types=custom"
    )
    attachments, attach_task, disconnect_attach = request(
        harness.app, "GET", path, headers=AUTH, query="types=attachment"
    )
    await wait_for(custom, until_ready)
    await wait_for(attachments, until_ready)

    notebook.emit("marimo.test", {"hello": 1})
    await wait_for(custom, lambda response: "custom" in response.names())
    frame = next(r for r in custom.records if r.get("event") == "custom")
    message = msgspec.convert(frame["data"], protocol.CustomMessage)
    assert message.custom == protocol.Custom(
        type="marimo.test", data={"hello": 1}
    )
    assert "custom" not in attachments.names()

    disconnect_custom()
    disconnect_attach()
    await asyncio.gather(custom_task, attach_task)


@pytest.mark.parametrize(
    ("header", "value"),
    [
        (api_module.ATTACHMENT_IDENTITY, ""),
        (api_module.ATTACHMENT_KIND, "Agent"),
        (api_module.ATTACHMENT_NAME, "n" * 257),
    ],
)
async def test_invalid_attachment_headers_are_rejected(
    harness: Harness, header: str, value: str
) -> None:
    response = await finished(
        harness.app,
        "GET",
        f"/notebooks/{harness.notebook_id}/events",
        headers={**AUTH, header: value},
    )
    assert response.status == 400
    body = response.json()
    assert body["type"].endswith("/invalid-request")
    assert body["detail"] == f"{header} is invalid"


async def test_runtime_lifecycle_over_http(harness: Harness) -> None:
    app, nid = harness.app, harness.notebook_id
    path = f"/notebooks/{nid}/runtime"

    started = await finished(app, "PUT", path, headers=key("k1"), body=b"{}")
    assert started.status == 202
    assert started.json()["status"] == "starting"
    assert harness.backend().calls == [("start", started.json()["id"])]

    again = await finished(app, "PUT", path, headers=key("k2"), body=b"{}")
    assert again.status == 200
    assert again.json()["id"] == started.json()["id"]

    restart = await finished(app, "POST", path + "/restart", headers=key("k3"))
    assert restart.status == 409
    assert restart.json()["type"].endswith("/conflict")

    (await harness.host.notebook(nid)).observe(
        be.Running(runtime_id_of(await harness.host.notebook(nid)), "0.25.0")
    )
    restart = await finished(app, "POST", path + "/restart", headers=key("k4"))
    assert restart.status == 202
    assert restart.json()["status"] == "starting"
    assert restart.json()["id"] != started.json()["id"]

    (await harness.host.notebook(nid)).observe(
        be.Exited(runtime_id_of(await harness.host.notebook(nid)))
    )
    (await harness.host.notebook(nid)).observe(
        be.Running(runtime_id_of(await harness.host.notebook(nid)), "0.25.0")
    )
    stopped = await finished(app, "DELETE", path, headers=key("k5"))
    assert stopped.status == 202
    assert stopped.json()["status"] == "terminating"
    assert stopped.json()["id"] != started.json()["id"]
    assert stopped.json()["id"] == restart.json()["id"]

    (await harness.host.notebook(nid)).observe(
        be.Exited(runtime_id_of(await harness.host.notebook(nid)))
    )
    gone = await finished(app, "DELETE", path, headers=key("k6"))
    assert gone.status == 409
    assert gone.json()["type"].endswith("/no-runtime")


async def test_slow_restart_keeps_its_receipt(harness: Harness) -> None:
    nid = await harness.running()
    notebook = await harness.host.notebook(nid)
    path = f"/notebooks/{nid}/runtime/restart"
    accepted = await finished(
        harness.app, "POST", path, headers=key("restart")
    )
    assert accepted.status == 202

    # The receipt's 30-second window must not begin during shutdown/startup.
    harness.now = 100
    harness.app.state.host_context.expire()
    notebook.observe(be.Exited(runtime_id_of(notebook)))
    notebook.observe(be.Running(runtime_id_of(notebook), "0.25.0"))
    calls = list(harness.backend().calls)

    retried = await finished(harness.app, "POST", path, headers=key("restart"))
    assert (retried.status, retried.json(), harness.backend().calls) == (
        accepted.status,
        accepted.json(),
        calls,
    )

    harness.now = 129
    retried = await finished(harness.app, "POST", path, headers=key("restart"))
    assert (retried.json(), harness.backend().calls) == (
        accepted.json(),
        calls,
    )
    harness.now = 130
    fresh = await finished(harness.app, "POST", path, headers=key("restart"))
    assert fresh.status == 202
    assert fresh.json()["id"] != accepted.json()["id"]
    assert harness.backend().calls == [*calls, ("stop", accepted.json()["id"])]


@pytest.mark.parametrize(
    ("operation", "failed"),
    [
        ("start", False),
        ("start", True),
        ("stop", False),
        ("restart", False),
        ("restart", True),
    ],
)
async def test_lifecycle_receipts_expire_after_terminal_events(
    harness: Harness, operation: str, failed: bool
) -> None:
    nid = harness.notebook_id
    if operation != "start":
        await harness.running()
    notebook = await harness.host.notebook(nid)
    context = harness.app.state.host_context
    listeners = list(harness.host._stream._listeners)
    method = {"start": "PUT", "stop": "DELETE", "restart": "POST"}[operation]
    path = f"/notebooks/{nid}/runtime"
    if operation == "restart":
        path += "/restart"
    accepted = await finished(
        harness.app, method, path, headers=key("lifecycle")
    )
    assert accepted.status == 202
    for now in (100, 200):
        harness.now = now
        context.expire()
        calls = list(harness.backend().calls)
        replayed = await finished(
            harness.app, method, path, headers=key("lifecycle")
        )
        assert (replayed.status, replayed.json(), harness.backend().calls) == (
            202,
            accepted.json(),
            calls,
        )
        if operation == "restart" and now == 100:
            notebook.observe(be.Exited(runtime_id_of(notebook)))
    rid = runtime_id_of(notebook)
    notebook.observe(
        be.Exited(rid, "failed" if failed else None)
        if failed or operation == "stop"
        else be.Running(rid)
    )
    assert harness.host._stream._listeners == listeners
    calls = list(harness.backend().calls)
    harness.now = 229
    context.expire()
    replayed = await finished(
        harness.app, method, path, headers=key("lifecycle")
    )
    assert (replayed.status, replayed.json(), harness.backend().calls) == (
        202,
        accepted.json(),
        calls,
    )
    harness.now = 230
    assert context.remembered("lifecycle") is None


@pytest.mark.parametrize(
    "operation", ["start", "stop", "restart", "replacement"]
)
async def test_stop_settles_superseded_lifecycle_receipts(
    harness: Harness, operation: str
) -> None:
    nid = harness.notebook_id
    if operation != "start":
        await harness.running()
    notebook = await harness.host.notebook(nid)
    context = harness.app.state.host_context
    listeners = list(harness.host._stream._listeners)
    path = f"/notebooks/{nid}/runtime"
    method = "PUT" if operation == "start" else "DELETE"
    pending_path = path
    if operation in {"restart", "replacement"}:
        method, pending_path = "POST", path + "/restart"
    accepted = await finished(
        harness.app, method, pending_path, headers=key("pending")
    )
    if operation == "replacement":
        notebook.observe(be.Exited(runtime_id_of(notebook)))
    harness.now = 100
    stops = [
        await finished(harness.app, "DELETE", path, headers=key(request_id))
        for request_id in ("stop-1", "stop-2")
    ]
    harness.now = 200
    notebook.observe(be.Exited(runtime_id_of(notebook)))
    assert harness.host._stream._listeners == listeners
    calls = list(harness.backend().calls)
    harness.now = 229
    context.expire()
    for request_id, verb, url, response in [
        ("pending", method, pending_path, accepted),
        ("stop-1", "DELETE", path, stops[0]),
        ("stop-2", "DELETE", path, stops[1]),
    ]:
        replayed = await finished(
            harness.app, verb, url, headers=key(request_id)
        )
        assert (replayed.status, replayed.json(), harness.backend().calls) == (
            202,
            response.json(),
            calls,
        )
    harness.now = 230
    assert [
        context.remembered(request_id)
        for request_id in ("pending", "stop-1", "stop-2")
    ] == [None, None, None]


@pytest.mark.parametrize(
    "operation", ["start", "stop", "restart", "failed-stop"]
)
async def test_synchronous_lifecycle_completion(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    nid = harness.notebook_id
    if operation != "start":
        await harness.running()
    notebook = await harness.host.notebook(nid)
    if operation == "failed-stop":
        notebook.observe(be.Exited(runtime_id_of(notebook), "failed"))
    backend = harness.backend()
    start, stop = backend.start, backend.stop

    def start_immediately(rid: str) -> None:
        start(rid)
        notebook.observe(be.Running(protocol.RuntimeId(rid)))

    def stop_immediately(rid: str) -> None:
        stop(rid)
        notebook.observe(be.Exited(protocol.RuntimeId(rid)))

    monkeypatch.setattr(backend, "start", start_immediately)
    monkeypatch.setattr(backend, "stop", stop_immediately)
    listeners = list(harness.host._stream._listeners)
    method = "PUT" if operation == "start" else "DELETE"
    path = f"/notebooks/{nid}/runtime"
    if operation == "restart":
        method, path = "POST", path + "/restart"
    accepted = await finished(
        harness.app, method, path, headers=key("immediate")
    )
    assert accepted.status == 202
    assert harness.host._stream._listeners == listeners
    calls = list(backend.calls)
    harness.now = 29
    replayed = await finished(
        harness.app, method, path, headers=key("immediate")
    )
    assert (replayed.status, replayed.json(), backend.calls) == (
        202,
        accepted.json(),
        calls,
    )
    harness.now = 30
    assert harness.app.state.host_context.remembered("immediate") is None


async def test_noop_and_rejected_lifecycle_requests_release_their_listeners(
    harness: Harness,
) -> None:
    nid = await harness.running()
    context = harness.app.state.host_context
    listeners = list(harness.host._stream._listeners)
    path = f"/notebooks/{nid}/runtime"
    existing = await finished(
        harness.app, "PUT", path, headers=key("existing")
    )
    assert existing.status == 200
    assert harness.host._stream._listeners == listeners
    rejected = await finished(
        harness.app, "PUT", path, headers=key("invalid"), body=b"{"
    )
    assert rejected.status == 400
    assert context.remembered("invalid") is None
    assert harness.host._stream._listeners == listeners
    harness.now = 30
    assert context.remembered("existing") is None


async def test_run_filter_over_http(harness: Harness) -> None:
    nid = await harness.running()
    notebook = await harness.host.notebook(nid)
    first = notebook.run("1", request_id="first")
    notebook.observe(
        be.Planned(
            first.id,
            (be.PlannedExecution(protocol.ExecutionId("e1"), None, "h", "1"),),
        )
    )
    notebook.observe(
        be.Concluded(protocol.ExecutionId("e1"), protocol.ValueOutcome(None))
    )
    notebook.observe(be.Status(protocol.ExecutionId("e1"), "completed"))
    notebook.observe(be.Done(first.id, "succeeded"))
    notebook.run("2", request_id="second")
    response, task, disconnect = request(
        harness.app,
        "GET",
        f"/notebooks/{nid}/events",
        headers=AUTH,
        query=f"run_id={first.id}&types=run",
    )
    try:
        await wait_for(response, until_ready)
        assert response.names() == ["run", "ready"]
        assert response.records[0]["data"]["run"]["id"] == first.id
    finally:
        disconnect()
        await asyncio.wait_for(task, 5)
    invalid = await finished(
        harness.app,
        "GET",
        f"/notebooks/{nid}/events",
        headers=AUTH,
        query="run_id=",
    )
    assert invalid.status == 400


async def test_interrupting_an_unstarted_run_after_shutdown(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    nid = await harness.running()
    runs = f"/notebooks/{nid}/runtime/runs"
    accepted = await finished(
        harness.app, "POST", runs, headers=key("queued"), body=b'{"code":"1"}'
    )
    assert accepted.status == 202
    run_id = accepted.json()["id"]
    notebook = await harness.host.notebook(nid)
    runtime_id = runtime_id_of(notebook)
    notebook.stop()
    notebook.observe(be.Exited(runtime_id))

    def snapshot_unavailable(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("run lookup must not build a snapshot")

    monkeypatch.setattr(harness.host, "events", snapshot_unavailable)
    completed = await finished(
        harness.app, "DELETE", f"{runs}/{run_id}", headers=key("completed")
    )
    assert completed.status == 409
    unknown = await finished(
        harness.app, "DELETE", f"{runs}/unknown", headers=key("unknown")
    )
    assert unknown.status == 404
    harness.now = 61
    harness.host.expire()
    expired = await finished(
        harness.app, "DELETE", f"{runs}/{run_id}", headers=key("expired")
    )
    assert expired.status == 404


async def test_scratch_runs_over_http(harness: Harness) -> None:
    app, nid = harness.app, harness.notebook_id
    runs = f"/notebooks/{nid}/runtime/runs"
    body = json.dumps({"code": "3 * 3"}).encode()

    refused = await finished(app, "POST", runs, headers=key("r0"), body=body)
    assert refused.status == 409
    assert refused.json()["type"].endswith("/no-runtime")

    await harness.running()
    accepted = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert accepted.status == 202
    run_id = accepted.json()["id"]
    assert accepted.json()["status"] == "queued"
    assert harness.backend().calls[-1] == ("run", run_id, "3 * 3")

    repeated = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert repeated.status == 202
    assert repeated.body == accepted.body
    assert harness.backend().calls.count(("run", run_id, "3 * 3")) == 1
    notebook = await harness.host.notebook(nid)
    notebook.observe(
        be.Planned(run_id, (be.PlannedExecution("e1", None, "hash", "3 * 3"),))
    )
    notebook.observe(be.Status("e1", "running"))
    running = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert running.json()["status"] == "running"
    reused = await finished(
        app,
        "POST",
        runs,
        headers=key("r1"),
        body=json.dumps({"code": "4"}).encode(),
    )
    assert reused.status == 409

    busy = await finished(app, "POST", runs, headers=key("r2"), body=body)
    assert busy.status == 409
    assert run_id in busy.json()["detail"]

    interrupted = await finished(
        app, "DELETE", f"{runs}/{run_id}", headers=key("i1")
    )
    assert interrupted.status == 202
    assert harness.backend().calls[-1] == ("interrupt", run_id)

    notebook.observe(be.Concluded("e1", protocol.InterruptedOutcome()))
    notebook.observe(be.Status("e1", "completed"))
    notebook.observe(be.Done(run_id, "interrupted"))
    completed = await finished(app, "POST", runs, headers=key("r1"), body=body)
    assert completed.json()["status"] == "completed"
    assert completed.json()["outcome"] == "interrupted"
    assert completed.json()["completed_at"] is not None
    late = await finished(app, "DELETE", f"{runs}/{run_id}", headers=key("i2"))
    assert late.status == 409
    missing = await finished(app, "DELETE", runs + "/zz", headers=key("i3"))
    assert missing.status == 404

    invalid = await finished(app, "POST", runs, headers=key("r3"), body=b"{}")
    assert invalid.status == 400
    malformed = await finished(app, "POST", runs, headers=key("r4"), body=b"{")
    assert malformed.status == 400
    assert malformed.json()["type"].endswith("/invalid-request")
    unkeyed = await finished(app, "POST", runs, headers=AUTH, body=body)
    assert unkeyed.status == 400


@pytest.mark.parametrize(
    "harness",
    [RetentionPolicy(ephemeral_seconds=10)],
    indirect=True,
)
@pytest.mark.parametrize("cell_id", [None, "a"])
async def test_request_receipts_expire_independently_of_results(
    harness: Harness, cell_id: str | None
) -> None:
    nid = await harness.running()
    notebook = await harness.host.notebook(nid)
    path = f"/notebooks/{nid}/runtime/runs"
    body = b'{"code":"42"}'
    accepted = await finished(
        harness.app, "POST", path, headers=key("run"), body=body
    )
    run_id = protocol.RunId(accepted.json()["id"])
    eid = protocol.ExecutionId("execution")
    notebook.observe(
        be.Planned(run_id, (be.PlannedExecution(eid, cell_id, "hash", "42"),))
    )
    notebook.observe(be.Status(eid, "running"))
    harness.now = 100
    active = await finished(
        harness.app, "POST", path, headers=key("run"), body=body
    )
    assert active.json()["id"] == run_id
    assert active.json()["status"] == "running"
    notebook.observe(be.Concluded(eid, protocol.ValueOutcome(None)))
    notebook.observe(be.Status(eid, "completed"))
    notebook.observe(be.Done(run_id, "succeeded"))
    harness.now = 129
    harness.host.expire()
    replayed = await finished(
        harness.app, "POST", path, headers=key("run"), body=body
    )
    assert replayed.json()["id"] == run_id
    assert replayed.json()["status"] == "completed"
    assert replayed.json()["outcome"] == "succeeded"
    assert any(
        event.kind == "execution"
        for event in harness.host.events(notebook_id=nid)
    ) == (cell_id is not None)
    conflicting = await finished(
        harness.app, "POST", path, headers=key("run"), body=b'{"code":"43"}'
    )
    assert conflicting.status == 409

    harness.now = 130
    fresh = await finished(
        harness.app, "POST", path, headers=key("run"), body=b'{"code":"43"}'
    )
    assert fresh.status == 202
    assert fresh.json()["id"] != run_id
    assert [call for call in harness.backend().calls if call[0] == "run"] == [
        ("run", run_id, "42"),
        ("run", fresh.json()["id"], "43"),
    ]


@pytest.mark.parametrize("cancel_waiter", [False, True])
async def test_concurrent_retries_share_the_mutation(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, cancel_waiter: bool
) -> None:
    started, release = asyncio.Event(), asyncio.Event()
    create = harness.bridge.create

    async def delayed_create(
        target: Path, *, name: str | None, request_id: str
    ) -> protocol.Notebook:
        started.set()
        await release.wait()
        return await create(target, name=name, request_id=request_id)

    monkeypatch.setattr(harness.bridge, "create", delayed_create)
    body = json.dumps(
        {"project_id": harness.bridge.index.project_id, "path": "new.py"}
    ).encode()
    first, first_task, _ = request(
        harness.app, "POST", "/notebooks", headers=key("create"), body=body
    )
    await asyncio.wait_for(started.wait(), 5)
    try:
        conflicting = await finished(
            harness.app,
            "POST",
            "/notebooks",
            headers=key("create"),
            body=json.dumps(
                {
                    "project_id": harness.bridge.index.project_id,
                    "path": "other.py",
                }
            ).encode(),
        )
        assert conflicting.status == 409
        if cancel_waiter:
            first_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first_task
        retry, retry_task, _ = request(
            harness.app, "POST", "/notebooks", headers=key("create"), body=body
        )
        # Queue the release after the retry has entered the request handler.
        asyncio.get_running_loop().call_soon(release.set)
        await asyncio.wait_for(retry_task, 5)
        assert retry.status == 201
        if not cancel_waiter:
            await asyncio.wait_for(first_task, 5)
            assert first.body == retry.body
        assert (harness.root / "new.py").exists()
        assert not (harness.root / "other.py").exists()
        assert sorted(n.path for n in harness.host.notebooks.values()) == [
            "forecasts.py",
            "new.py",
        ]
    finally:
        release.set()
        await asyncio.gather(first_task, return_exceptions=True)


async def test_rejected_mutations_do_not_reserve_the_key(
    harness: Harness,
) -> None:
    path = f"/notebooks/{harness.notebook_id}"
    rejected = await finished(
        harness.app,
        "PATCH",
        path,
        headers=key("move"),
        body=b'{"path":"forecasts.py"}',
    )
    assert rejected.status == 409
    corrected = await finished(
        harness.app,
        "PATCH",
        path,
        headers=key("move"),
        body=b'{"path":"corrected.py"}',
    )
    assert corrected.status == 200
    assert corrected.json()["path"] == "corrected.py"
    assert (harness.root / "corrected.py").exists()
    assert not (harness.root / "forecasts.py").exists()


async def test_create_update_and_delete_notebooks(harness: Harness) -> None:
    app, root = harness.app, harness.root
    project = harness.bridge.index.project_id

    created = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c1"),
        body=json.dumps(
            {"project_id": project, "path": "new/one.py"}
        ).encode(),
    )
    assert created.status == 201, created.body
    record = created.json()
    assert record["path"] == str(Path("new") / "one.py")
    assert record["name"] == "one"
    assert (root / "new" / "one.py").read_text().startswith("import marimo")
    assert record["id"] in harness.host.notebooks

    again = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c2"),
        body=json.dumps(
            {"project_id": project, "path": "new/one.py"}
        ).encode(),
    )
    assert again.status == 409
    escaped = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c3"),
        body=json.dumps({"project_id": project, "path": "../x.py"}).encode(),
    )
    assert escaped.status == 400
    elsewhere = await finished(
        app,
        "POST",
        "/notebooks",
        headers=key("c4"),
        body=json.dumps({"project_id": "nope", "path": "y.py"}).encode(),
    )
    assert elsewhere.status == 404

    moved = await finished(
        app,
        "PATCH",
        f"/notebooks/{record['id']}",
        headers=key("u1"),
        body=json.dumps({"path": "two.py", "name": "Two"}).encode(),
    )
    assert moved.status == 200, moved.body
    assert moved.json()["path"] == "two.py"
    assert moved.json()["name"] == "Two"
    assert (root / "two.py").exists()
    assert not (root / "new" / "one.py").exists()
    harness.bridge.index.refresh()
    assert harness.host.notebooks[record["id"]].name == "Two"

    onto = await finished(
        app,
        "PATCH",
        f"/notebooks/{record['id']}",
        headers=key("u2"),
        body=json.dumps({"path": "forecasts.py"}).encode(),
    )
    assert onto.status == 409

    deleted = await finished(
        app, "DELETE", f"/notebooks/{record['id']}", headers=key("d1")
    )
    assert deleted.status == 204
    assert not (root / "two.py").exists()
    assert record["id"] not in harness.host.notebooks

    repeated = await finished(
        app, "DELETE", f"/notebooks/{record['id']}", headers=key("d1")
    )
    assert repeated.status == 204
    assert repeated.body == deleted.body == b""

    await harness.running()
    busy = await finished(
        app, "DELETE", f"/notebooks/{harness.notebook_id}", headers=key("d2")
    )
    assert busy.status == 409


async def test_open_selects_the_notebook_outside_the_working_directory(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = harness.root / "forecasts.py"
    workspace = SingleFileWorkspace(MarimoFile(name=file.name, path=str(file)))
    harness.app.state.session_manager.workspace = workspace
    launch = harness.root / "launch"
    launch.mkdir()
    (launch / file.name).write_text("another notebook")
    monkeypatch.chdir(launch)
    opened: list[str] = []
    ready = threading.Event()

    def open_browser(_browser: str, url: str) -> None:
        opened.append(url)
        ready.set()

    monkeypatch.setattr(api_module, "open_url_in_browser", open_browser)
    response = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/open",
        headers=key("o1"),
    )

    assert response.status == 200
    url = response.json()["url"]
    query = parse_qs(urlsplit(url).query)
    assert workspace.resolve(query["file"][0]) == str(file)
    assert query["access_token"] == ["fake-token"]
    assert TOKEN not in url
    assert await asyncio.to_thread(ready.wait, 5)
    assert opened == [url]


async def test_operations_the_host_does_not_offer_are_501(
    harness: Harness,
) -> None:
    notebook = await harness.host.notebook(harness.notebook_id)
    host = Host(operations=[])
    [project] = [
        e.data.project
        for e in harness.host.events()
        if isinstance(e.data, ProjectMessage)
    ]
    host.update_project(project)
    host.add_notebook(harness.host.notebooks[notebook.id], make_notebook)
    harness.bridge.host = host
    response = await finished(
        harness.app,
        "PUT",
        f"/notebooks/{notebook.id}/runtime",
        headers=key("x1"),
    )
    assert response.status == 501
    assert response.json()["type"].endswith("/unsupported-operation")


async def test_competing_moves_preserve_both_notebooks(
    harness: Harness,
) -> None:
    first = harness.root / "forecasts.py"
    second = harness.root / "second.py"
    first.write_text("first notebook")
    second.write_text("second notebook")
    other = harness.bridge.index.ensure(str(second))
    assert other is not None
    ids = [harness.notebook_id, other.id]

    responses = await asyncio.gather(
        *(
            finished(
                harness.app,
                "PATCH",
                f"/notebooks/{nid}",
                headers=key(f"move-{i}"),
                body=b'{"path":"destination.py"}',
            )
            for i, nid in enumerate(ids)
        )
    )

    assert sorted(r.status for r in responses) == [200, 409]
    records = [harness.host.notebooks[nid] for nid in ids]
    assert len({record.path for record in records}) == 2
    assert {
        (harness.root / record.path).read_text()
        for record in records
        if record.path is not None
    } == {"first notebook", "second notebook"}


@pytest.mark.parametrize("operation", ["create", "move"])
async def test_symlink_escape_has_no_filesystem_side_effects(
    harness: Harness, tmp_path: Path, operation: str
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (harness.root / "link").symlink_to(outside, target_is_directory=True)
    source = harness.root / "forecasts.py"
    original = source.read_text()
    if operation == "create":
        response = await finished(
            harness.app,
            "POST",
            "/notebooks",
            headers=key("escape"),
            body=json.dumps(
                {
                    "project_id": harness.bridge.index.project_id,
                    "path": "link/nested/new.py",
                }
            ).encode(),
        )
    else:
        response = await finished(
            harness.app,
            "PATCH",
            f"/notebooks/{harness.notebook_id}",
            headers=key("escape"),
            body=b'{"path":"link/nested/new.py"}',
        )
    assert response.status == 409
    assert list(outside.iterdir()) == []
    assert source.read_text() == original
    assert [n.path for n in harness.host.notebooks.values()] == [
        "forecasts.py"
    ]


NOTEBOOK = """import marimo

__generated_with = "0.0.0"
app = marimo.App(width="full")


@app.cell
def _():
    x = 21
    return (x,)


@app.cell(hide_code=True)
def _(x):
    y = x * 2
    return


if __name__ == "__main__":
    app.run()
"""


@pytest.mark.parametrize("preanalyzed", [False, True])
async def test_the_notebook_stream_carries_cells_then_the_document(
    harness: Harness,
    preanalyzed: bool,
) -> None:
    (harness.root / "forecasts.py").write_text(NOTEBOOK)
    if preanalyzed:
        await analyzed(await harness.host.notebook(harness.notebook_id))
    response, _, disconnect = request(
        harness.app,
        "GET",
        f"/notebooks/{harness.notebook_id}/events",
        headers=AUTH,
    )
    await wait_for(
        response, lambda r: until_ready(r) and "analysis" in r.names()
    )
    disconnect()

    # Analysis follows the document, but can finish before or after ready.
    names = response.names()
    assert [name for name in names if name != "analysis"] == [
        "notebook",
        "cell",
        "cell",
        "document",
        "attachment",
        "ready",
    ]
    assert names.count("analysis") == 1
    assert names.index("analysis") > names.index("document")
    first, second = (r["data"]["cell"] for r in response.records[1:3])
    document = response.records[3]["data"]["document"]
    analysis = response.records[names.index("analysis")]["data"]["analysis"]
    assert first["code"] == "x = 21"
    assert second["code"] == "y = x * 2"
    assert second["config"]["hide_code"] is True
    assert document["order"] == [first["id"], second["id"]]
    assert document["app_config"] == {"width": "full"}
    assert "policy" not in document
    assert document["saved_etag"] == document["etag"]
    assert all(
        c["notebook_id"] == harness.notebook_id for c in (first, second)
    )
    assert analysis["notebook_id"] == harness.notebook_id
    assert analysis["document_etag"] == document["etag"]
    assert analysis["cells"] == {
        first["id"]: {"defs": ["x"], "refs": [], "errors": []},
        second["id"]: {"defs": ["y"], "refs": ["x"], "errors": []},
    }

    # A filtered stream is a snapshot of the document alone, and a second
    # connection reuses the loaded document.
    response, _, disconnect = request(
        harness.app,
        "GET",
        f"/notebooks/{harness.notebook_id}/events",
        headers=AUTH,
        query="types=cell,document",
    )
    await wait_for(response, until_ready)
    disconnect()
    assert response.names() == ["cell", "cell", "document", "ready"]
    assert response.records[2]["data"]["document"] == document


async def test_an_unreadable_notebook_stays_in_the_catalog_and_can_retry(
    harness: Harness,
) -> None:
    file = harness.root / "forecasts.py"
    file.write_text("print('not a notebook')\n")
    notebook_id = harness.notebook_id

    response = await finished(
        harness.app,
        "GET",
        f"/notebooks/{notebook_id}/events",
        headers=AUTH,
    )
    assert response.status == 409
    assert harness.host.peek_notebook(notebook_id) is None
    assert notebook_id in harness.host.notebooks
    assert harness.backends == {}

    file.write_text(NOTEBOOK)
    notebook = await harness.host.notebook(notebook_id)
    assert [cell.code for cell in notebook.document] == [
        "x = 21",
        "y = x * 2",
    ]


async def test_deleting_an_unreadable_notebook_does_not_initialize_it(
    harness: Harness,
) -> None:
    file = harness.root / "forecasts.py"
    file.write_text("print('not a notebook')\n")
    notebook_id = harness.notebook_id
    response = await finished(
        harness.app,
        "DELETE",
        f"/notebooks/{notebook_id}",
        headers=key("delete-unreadable"),
    )
    assert response.status == 204
    assert notebook_id not in harness.host.notebooks
    assert not file.exists()
    assert harness.backends == {}


def edit_body(*changes: dict[str, object]) -> bytes:
    return json.dumps({"changes": list(changes)}).encode()


async def opened(harness: Harness) -> tuple[Response, Callable[[], None]]:
    """Open the notebook's stream past `ready`, returning it and its closer."""
    (harness.root / "forecasts.py").write_text(NOTEBOOK)
    response, _, disconnect = request(
        harness.app,
        "GET",
        f"/notebooks/{harness.notebook_id}/events",
        headers=AUTH,
    )
    await wait_for(response, until_ready)
    return response, disconnect


def first_record(stream: Response, event: str) -> dict[str, Any]:
    return next(r["data"] for r in stream.records if r.get("event") == event)


async def test_an_edit_reaches_the_stream_as_one_unit(
    harness: Harness,
) -> None:
    stream, disconnect = await opened(harness)
    document = first_record(stream, "document")["document"]
    first_id = document["order"][0]
    # The first revision's analysis arrives off the event loop.
    await wait_for(stream, lambda r: "analysis" in r.names())
    seen = len(stream.records)

    edited = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/edits",
        headers=key("edit-1"),
        body=edit_body(
            {
                "kind": "put_cell",
                "base_etag": None,
                "after": first_id,
                "cell": {"id": "fresh", "code": "z = 3"},
            }
        ),
    )
    assert edited.status == 200, edited.body
    response = edited.json()
    assert set(response["cells"]) == {"fresh"}
    assert response["document"]["order"][1] == "fresh"
    assert response["document"]["saved_etag"] == document["etag"]
    assert response["document"]["etag"] != document["etag"]

    await wait_for(stream, lambda r: r.names().count("analysis") >= 2)
    after = [r for r in stream.records[seen:] if "event" in r]
    assert [r["event"] for r in after] == ["cell", "document", "analysis"]
    assert all(r["data"]["request_id"] == "edit-1" for r in after)
    assert (
        after[0]["data"]["cell"]["etag"] == response["cells"]["fresh"]["etag"]
    )
    assert after[1]["data"]["document"] == response["document"]
    analysis = after[2]["data"]["analysis"]
    assert analysis["document_etag"] == response["document"]["etag"]
    assert analysis["cells"]["fresh"]["defs"] == ["z"]
    assert "z = 3" not in (harness.root / "forecasts.py").read_text()
    disconnect()


async def test_a_stale_etag_is_a_conflict_that_changes_nothing(
    harness: Harness,
) -> None:
    stream, disconnect = await opened(harness)
    disconnect()
    cell = first_record(stream, "cell")["cell"]
    document = first_record(stream, "document")["document"]

    refused = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/edits",
        headers=key("edit-stale"),
        body=edit_body(
            {
                "kind": "put_cell",
                "base_etag": None,
                "cell": {"id": "new", "code": "1"},
            },
            {
                "kind": "put_cell",
                "base_etag": "0000000000000000",
                "cell": {"id": cell["id"], "code": "x = 99"},
            },
        ),
    )
    assert refused.status == 409
    problem = refused.json()
    assert problem["type"].endswith("/conflict")
    assert problem["edit"]["change"] == 1
    assert problem["edit"]["cell"]["etag"] == cell["etag"]
    assert problem["edit"]["document"]["etag"] == document["etag"]

    invalid = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/edits",
        headers=key("edit-invalid"),
        body=edit_body(
            {"kind": "set_order", "base_etag": "*", "order": [cell["id"]]},
        ),
    )
    assert invalid.status == 400
    assert invalid.json()["type"].endswith("/invalid-request")

    again, disconnect = await opened(harness)
    disconnect()
    assert (
        first_record(again, "document")["document"]["etag"] == document["etag"]
    )


async def test_save_writes_the_file_and_reports_the_saved_revision(
    harness: Harness,
) -> None:
    stream, disconnect = await opened(harness)
    document = first_record(stream, "document")["document"]
    first_id = document["order"][0]
    edited = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/edits",
        headers=key("edit-1"),
        body=edit_body(
            {
                "kind": "put_cell",
                "base_etag": None,
                "after": first_id,
                "cell": {"id": "fresh", "code": "z = 3"},
            }
        ),
    )
    assert edited.status == 200, edited.body
    etag = edited.json()["document"]["etag"]
    assert "z = 3" not in (harness.root / "forecasts.py").read_text()

    # A weak validator never matches, even one naming the current etag.
    for header in ('"stale"', "W/stale, other", f'W/"{etag}"'):
        stale = await finished(
            harness.app,
            "POST",
            f"/notebooks/{harness.notebook_id}/save",
            headers={**key(f"save-{header}"), "If-Match": header},
            body=b"{}",
        )
        assert stale.status == 409, stale.body
        assert stale.json()["edit"]["change"] == 0
        assert stale.json()["edit"]["document"]["etag"] == etag

    saved = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/save",
        headers={**key("save-1"), "If-Match": f'W/"other", "{etag}"'},
        body=b"{}",
    )
    assert saved.status == 200, saved.body
    assert saved.json()["document"]["saved_etag"] == etag
    text = (harness.root / "forecasts.py").read_text()
    assert "z = 3" in text
    assert 'width="full"' in text
    await wait_for(
        stream,
        lambda r: any(
            x.get("event") == "document"
            and x["data"]["document"]["saved_etag"] == etag
            and x["data"]["request_id"] == "save-1"
            for x in r.records
        ),
    )

    # A retry under the same key with another precondition is another request.
    again = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/save",
        headers={**key("save-1"), "If-Match": '"stale"'},
        body=b"{}",
    )
    assert again.status == 409
    assert "another request" in again.json()["detail"]
    disconnect()


async def test_edits_during_a_save_remain_unsaved(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    notebook = await harness.host.notebook(harness.notebook_id)
    document = notebook.document
    written = document.etag
    started = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    original = AppFileManager.save_from_cells

    def save(self: AppFileManager, cells: Any, **kwargs: Any) -> str:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        return original(self, cells, **kwargs)

    monkeypatch.setattr(AppFileManager, "save_from_cells", save)
    saved, task, _ = request(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/save",
        headers=key("save-before-edit"),
        body=b"{}",
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        edited = await finished(
            harness.app,
            "POST",
            f"/notebooks/{harness.notebook_id}/edits",
            headers=key("edit-during-save"),
            body=edit_body(
                {
                    "kind": "put_cell",
                    "base_etag": None,
                    "cell": {"id": "new", "code": "new_value = 42"},
                }
            ),
        )
        assert edited.status == 200, edited.body
    finally:
        release.set()
        await asyncio.wait_for(task, 5)

    assert saved.status == 200, saved.body
    assert saved.json()["document"] == {
        **edited.json()["document"],
        "saved_etag": written,
    }
    assert "new_value" not in (harness.root / "forecasts.py").read_text()


async def test_a_file_changed_outside_marimo_needs_a_decision(
    harness: Harness,
) -> None:
    stream, disconnect = await opened(harness)
    disconnect()
    cell = first_record(stream, "cell")["cell"]
    file = harness.root / "forecasts.py"
    edited = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/edits",
        headers=key("edit-1"),
        body=edit_body(
            {
                "kind": "put_cell",
                "base_etag": cell["etag"],
                "cell": {"id": cell["id"], "code": "x = 99"},
            }
        ),
    )
    assert edited.status == 200, edited.body
    file.write_text(file.read_text().replace("x = 21", "x = 22"))

    async def save(name: str, body: bytes) -> Response:
        return await finished(
            harness.app,
            "POST",
            f"/notebooks/{harness.notebook_id}/save",
            headers=key(name),
            body=body,
        )

    asked = await save("save-1", b"{}")
    assert asked.status == 409, asked.body
    problem = asked.json()
    assert problem["type"].endswith("/decision-required")
    assert [d["id"] for d in problem["decisions"]] == ["file"]
    assert [o["id"] for o in problem["decisions"][0]["options"]] == [
        "overwrite",
        "reload",
    ]
    assert "x = 22" in file.read_text()

    unknown = await save("save-2", b'{"decisions": {"file": "merge"}}')
    assert unknown.status == 400, unknown.body
    assert unknown.json()["type"].endswith("/invalid-request")

    reloaded = await save("save-3", b'{"decisions": {"file": "reload"}}')
    assert reloaded.status == 200, reloaded.body
    response = reloaded.json()
    assert response["document"]["saved_etag"] == response["document"]["etag"]
    assert set(response["cells"]) == {cell["id"]}
    document = (await harness.host.notebook(harness.notebook_id)).document
    assert document.cell(cell["id"]).code == "x = 22"  # type: ignore[union-attr]
    assert "x = 22" in file.read_text()

    # With the document back in step with the file, a plain save proceeds.
    edited = await finished(
        harness.app,
        "POST",
        f"/notebooks/{harness.notebook_id}/edits",
        headers=key("edit-2"),
        body=edit_body(
            {
                "kind": "put_cell",
                "base_etag": "*",
                "cell": {"id": cell["id"], "code": "x = 100"},
            }
        ),
    )
    assert edited.status == 200, edited.body
    file.write_text(file.read_text().replace("x = 22", "x = 23"))
    overwritten = await save("save-4", b'{"decisions": {"file": "overwrite"}}')
    assert overwritten.status == 200, overwritten.body
    assert "x = 100" in file.read_text()
    assert (await save("save-5", b"{}")).status == 200

    # The host's own writes are not changes, even when the file does not
    # read back as written: a new cell's id is not stored in the file.
    for n, base, code in ((6, None, "y = 1\n\n"), (7, "*", "y = 2")):
        edited = await finished(
            harness.app,
            "POST",
            f"/notebooks/{harness.notebook_id}/edits",
            headers=key(f"edit-{n}"),
            body=edit_body(
                {
                    "kind": "put_cell",
                    "base_etag": base,
                    "cell": {"id": "fresh", "code": code},
                }
            ),
        )
        assert edited.status == 200, edited.body
        assert (await save(f"save-{n}", b"{}")).status == 200
