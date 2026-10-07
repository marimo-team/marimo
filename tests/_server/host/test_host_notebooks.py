# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from starlette.testclient import TestClient

from marimo._host.host import Host
from marimo._host.model import Attachment, HostState, Notebook
from marimo._host.transitions import Detach, NotebookSeen, StartRuntime
from marimo._server.host import api
from marimo._server.host.context import HOST_API_PATH, HostContext
from marimo._server.host.index import WorkspaceIndex
from marimo._server.host.lifespan import OPERATIONS
from marimo._server.main import create_starlette_app
from marimo._server.workspace import DirectoryWorkspace
from marimo._types.ids import AttachmentId, NotebookId, RuntimeId
from tests._server.host import drive
from tests._server.host.drive import AUTHORITY, PORT
from tests._server.mocks import get_starlette_server_state_init

if TYPE_CHECKING:
    from collections.abc import Iterator

    from marimo._host.stream import Event
    from marimo._host.transitions import Action

TOKEN = "record-token"
NOW = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)
AUTH = {"Authorization": f"Bearer {TOKEN}"}
GONE = NotebookId("nb-gone")
FOLLOWER = AttachmentId("a-gone")

SOURCE = """import marimo

app = marimo.App()


@app.cell
def _():
    x = 1
    return (x,)


if __name__ == "__main__":
    app.run()
"""


class NoRuntime:
    sandbox = False

    def perform(self, action: Action) -> None:
        del action


@pytest.fixture
def served(
    tmp_path: Path,
) -> Iterator[tuple[TestClient, Host, WorkspaceIndex]]:
    (tmp_path / "forecasts.py").write_text(SOURCE)
    app = create_starlette_app(base_url="", enable_auth=True)
    get_starlette_server_state_init().apply(app.state)
    host = Host(HostState(), NoRuntime(), operations=OPERATIONS)
    index = WorkspaceIndex(
        host, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    )
    index.refresh()
    # A notebook whose file is gone but which a client still follows. The
    # attachment is what keeps it published; without one it would leave.
    follower = Attachment(FOLLOWER, "client", None, NOW)
    host.observe(
        NotebookSeen(
            Notebook(
                GONE,
                index.project_id,
                "gone",
                None,
                None,
                attachments={FOLLOWER: follower},
            )
        )
    )
    app.state.host_context = HostContext(
        host=host,
        runtime=NoRuntime(),  # type: ignore[arg-type]
        index=index,
        token=TOKEN,
        url=f"http://{AUTHORITY}{HOST_API_PATH}",
        port=PORT,
    )
    with TestClient(
        app, base_url=f"http://{AUTHORITY}", client=("127.0.0.1", 50000)
    ) as client:
        yield client, host, index


@pytest.fixture
def client(served: tuple[TestClient, Host, WorkspaceIndex]) -> TestClient:
    return served[0]


@pytest.fixture
def notebook_id(served: tuple[TestClient, Host, WorkspaceIndex]) -> NotebookId:
    return drive.notebook_id(served[1], Path("forecasts.py"))


def test_export_returns_the_source_and_names_where_outputs_came_from(
    client: TestClient, notebook_id: NotebookId
) -> None:
    path = f"{HOST_API_PATH}/notebooks/{notebook_id}/export"

    source = client.get(path, params={"format": "py"}, headers=AUTH)
    assert source.status_code == 200
    assert source.headers["content-type"].startswith("text/x-python")
    assert source.headers["marimo-outputs"] == "none"
    assert source.text == SOURCE

    html = client.get(path, params={"format": "html"}, headers=AUTH)
    assert html.status_code == 406
    assert html.json()["type"].endswith("/not-acceptable")

    bad = client.get(path, params={"format": "pdf"}, headers=AUTH)
    assert bad.status_code == 400

    missing = client.get(
        f"{HOST_API_PATH}/notebooks/nope/export?format=py", headers=AUTH
    )
    assert missing.status_code == 404
    gone = client.get(
        f"{HOST_API_PATH}/notebooks/{GONE}/export?format=py", headers=AUTH
    )
    assert gone.status_code == 409


def test_open_returns_the_browser_url_without_a_token(
    client: TestClient,
    notebook_id: NotebookId,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        api, "open_url_in_browser", lambda _b, url: opened.append(url)
    )

    response = client.post(
        f"{HOST_API_PATH}/notebooks/{notebook_id}/open",
        headers={**AUTH, "Idempotency-Key": "k"},
    )
    assert response.status_code == 200
    url = response.json()["url"]
    assert url == "http://localhost:1234/?file=forecasts.py"
    assert TOKEN not in url

    again = client.post(
        f"{HOST_API_PATH}/notebooks/{notebook_id}/open",
        headers={**AUTH, "Idempotency-Key": "k"},
    )
    assert again.json() == response.json()

    gone = client.post(
        f"{HOST_API_PATH}/notebooks/{GONE}/open",
        headers={**AUTH, "Idempotency-Key": "k2"},
    )
    assert gone.status_code == 409


def test_create_writes_an_empty_notebook_and_publishes_it(
    served: tuple[TestClient, Host, WorkspaceIndex], tmp_path: Path
) -> None:
    client, host, index = served
    received: list[Event] = []
    host.subscribe(received.append)
    body = {"project_id": index.project_id, "path": "new/analysis.py"}

    created = client.post(
        f"{HOST_API_PATH}/notebooks",
        json=body,
        headers={**AUTH, "Idempotency-Key": "c1"},
    )
    assert created.status_code == 201, created.text
    notebook = created.json()
    assert notebook["path"] == str(Path("new") / "analysis.py")
    assert notebook["title"] == "analysis"
    assert (
        (tmp_path / "new" / "analysis.py")
        .read_text()
        .startswith("import marimo")
    )
    [event] = received
    assert event.name == "notebook"
    assert event.data is not None
    assert event.data.request_id == "c1"

    again = client.post(
        f"{HOST_API_PATH}/notebooks",
        json=body,
        headers={**AUTH, "Idempotency-Key": "c1"},
    )
    assert again.json() == notebook

    duplicate = client.post(
        f"{HOST_API_PATH}/notebooks",
        json=body,
        headers={**AUTH, "Idempotency-Key": "c2"},
    )
    assert duplicate.status_code == 409

    escaping = client.post(
        f"{HOST_API_PATH}/notebooks",
        json={"project_id": index.project_id, "path": "../outside.py"},
        headers={**AUTH, "Idempotency-Key": "c3"},
    )
    assert escaping.status_code == 400


def test_delete_removes_the_file_unless_a_runtime_is_attached(
    served: tuple[TestClient, Host, WorkspaceIndex],
    notebook_id: NotebookId,
    tmp_path: Path,
) -> None:
    client, host, _ = served

    host.command(StartRuntime(notebook_id, RuntimeId("rt-1"), NOW, False))
    busy = client.delete(
        f"{HOST_API_PATH}/notebooks/{notebook_id}",
        headers={**AUTH, "Idempotency-Key": "d1"},
    )
    assert busy.status_code == 409
    assert (tmp_path / "forecasts.py").exists()

    gone = client.delete(
        f"{HOST_API_PATH}/notebooks/{GONE}",
        headers={**AUTH, "Idempotency-Key": "d2"},
    )
    assert gone.status_code == 204
    # Nothing to unlink, and the follower still refers to it. The notebook
    # leaves with its last attachment, as any fileless notebook does.
    assert GONE in host.state.notebooks
    host.observe(Detach(GONE, FOLLOWER))
    assert GONE not in host.state.notebooks

    unknown = client.delete(
        f"{HOST_API_PATH}/notebooks/nope",
        headers={**AUTH, "Idempotency-Key": "d3"},
    )
    assert unknown.status_code == 404


def test_update_moves_the_file_and_keeps_the_id(
    served: tuple[TestClient, Host, WorkspaceIndex],
    notebook_id: NotebookId,
    tmp_path: Path,
) -> None:
    client, host, index = served
    path = f"{HOST_API_PATH}/notebooks/{notebook_id}"

    moved = client.patch(
        path,
        json={"path": "models/forecasts_v2.py"},
        headers={**AUTH, "Idempotency-Key": "m1"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["id"] == notebook_id
    assert moved.json()["path"] == str(Path("models") / "forecasts_v2.py")
    assert not (tmp_path / "forecasts.py").exists()
    assert (tmp_path / "models" / "forecasts_v2.py").read_text() == SOURCE
    assert (
        drive.notebook_id(host, Path("models") / "forecasts_v2.py")
        == notebook_id
    )

    # A rescan agrees: the moved notebook is unchanged, and the fileless
    # one is still followed, so nothing is sent.
    received: list[Event] = []
    host.subscribe(received.append)
    index.refresh()
    assert received == []

    (tmp_path / "taken.py").write_text(SOURCE)
    taken = client.patch(
        path,
        json={"path": "taken.py"},
        headers={**AUTH, "Idempotency-Key": "m2"},
    )
    assert taken.status_code == 409

    escaping = client.patch(
        path,
        json={"path": "../out.py"},
        headers={**AUTH, "Idempotency-Key": "m3"},
    )
    assert escaping.status_code == 400
