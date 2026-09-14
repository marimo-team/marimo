# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest
from dirty_equals import IsStr, IsUUID
from inline_snapshot import snapshot
from starlette.testclient import TestClient

from marimo._ast.parse import parse_notebook
from marimo._server.discovery.models import CreateNotebookRequest
from marimo._server.files.directory_scanner import DirectoryScanner
from marimo._server.workspace import DirectoryWorkspace
from tests._server.discovery.test_api import _app

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("path", ["notebooks/café.py", "__new__.py"])
def test_create_empty_notebook(tmp_path: Path, path: str) -> None:
    app, manager = _app()
    manager.session_manager.workspace = DirectoryWorkspace(
        str(tmp_path), include_markdown=False
    )
    (tmp_path / "notebooks").mkdir()
    client = TestClient(
        app,
        client=("127.0.0.1", 50000),
        headers={"Authorization": f"Bearer {manager.token}"},
    )
    catalog = client.get("/api/marimo/v1/catalog").json()
    assert "notebook.create" in catalog["operations"]
    project_id = catalog["projects"][0]["id"]
    body = {
        "path": str((tmp_path / path).relative_to(tmp_path)),
        "project_id": project_id,
    }
    response = client.post("/api/marimo/v1/notebooks", json=body)
    assert response.status_code == 201, response.text
    assert response.json() == snapshot(
        {
            "id": IsUUID(),
            "project_id": IsUUID(),
            "path": IsStr(),
            "title": IsStr(),
            "openable": True,
            "sessions": [],
            "updated_at": IsStr(),
        }
    )
    assert response.json()["project_id"] == project_id
    assert response.json()["path"] == body["path"]
    assert response.json()["title"] == (tmp_path / path).name
    notebook = parse_notebook((tmp_path / body["path"]).read_text())
    assert notebook is not None
    assert notebook.valid
    assert all(not cell.code.strip() for cell in notebook.cells)
    assert not manager.session_manager.sessions
    created = response.json()
    opened = client.post(
        f"/api/marimo/v1/notebooks/{created['id']}/open"
    ).json()
    key = parse_qs(urlsplit(opened["uri"]).query)["file"][0]
    assert manager.session_manager.workspace.resolve(key) == str(
        tmp_path / path
    )
    created.pop("project_id")
    assert client.get("/api/marimo/v1/catalog").json()["projects"][0][
        "notebooks"
    ] == [created]


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("", 400),
        ("../escape.py", 400),
        ("absolute", 400),
        ("notebook.txt", 400),
        ("missing/notebook.py", 400),
        ("outside-link/notebook.py", 400),
        ("existing.py", 409),
        ("directory.py", 409),
    ],
)
def test_create_rejects_invalid_destination(
    tmp_path: Path, path: str, status: int
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "existing.py").write_text("preserve me")
    (root / "directory.py").mkdir()
    (root / "outside-link").symlink_to(tmp_path, target_is_directory=True)
    app, manager = _app()
    manager.session_manager.workspace = DirectoryWorkspace(
        str(root), include_markdown=False
    )
    client = TestClient(app, client=("127.0.0.1", 50000))
    headers = {"Authorization": f"Bearer {manager.token}"}
    project = client.get("/api/marimo/v1/catalog", headers=headers).json()[
        "projects"
    ][0]
    response = client.post(
        "/api/marimo/v1/notebooks",
        headers=headers,
        json={
            "path": str(root / "absolute.py") if path == "absolute" else path,
            "project_id": project["id"],
        },
    )
    assert response.status_code == status, response.text
    assert response.json() == {"message": IsStr()}
    assert (root / "existing.py").read_text() == "preserve me"
    assert sorted(p.name for p in root.iterdir()) == [
        "directory.py",
        "existing.py",
        "outside-link",
    ]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["workspace"]


def test_create_requires_authorization_and_directory_workspace(
    tmp_path: Path,
) -> None:
    app, manager = _app()
    client = TestClient(app, client=("127.0.0.1", 50000))
    headers = {"Authorization": f"Bearer {manager.token}"}
    body = {"path": "new.py", "project_id": "unknown"}
    assert (
        "notebook.create"
        not in client.get("/api/marimo/v1/catalog", headers=headers).json()[
            "operations"
        ]
    )
    assert (
        client.post(
            "/api/marimo/v1/notebooks", headers=headers, json=body
        ).status_code
        == 403
    )
    manager.session_manager.workspace = DirectoryWorkspace(
        str(tmp_path), include_markdown=False
    )
    assert (
        client.post("/api/marimo/v1/notebooks", json=body).status_code == 401
    )
    response = client.post(
        "/api/marimo/v1/notebooks", headers=headers, json={"path": "new.py"}
    )
    assert response.status_code == 400
    assert "project_id" in response.json()["message"]
    assert (
        client.post(
            "/api/marimo/v1/notebooks",
            headers=headers,
            json=body,
        ).status_code
        == 404
    )
    assert list(tmp_path.iterdir()) == []


async def test_created_notebook_remains_openable_beyond_scan_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(DirectoryScanner, "MAX_DEPTH", 0)
    (tmp_path / "nested").mkdir()
    _, manager = _app()
    manager.session_manager.workspace = DirectoryWorkspace(
        str(tmp_path), include_markdown=False
    )
    events = manager.watch()
    try:
        await anext(events)
        project = (await manager.catalog()).projects[0]
        created = await manager.create_notebook(
            CreateNotebookRequest(
                path="nested/notebook.py", project_id=project.id
            )
        )
        assert await asyncio.wait_for(anext(events), timeout=2.5) == (
            "event: catalog.changed\ndata: {}\n\n"
        )
        project = (await manager.catalog()).projects[0]
        assert project.truncated
        assert [notebook.id for notebook in project.notebooks] == [created.id]
        opened = await manager.open_notebook(created.id)
        assert parse_qs(urlsplit(opened.uri).query)["file"] == [
            str((tmp_path / "nested" / "notebook.py").relative_to(tmp_path))
        ]
        (tmp_path / "nested/notebook.py").unlink()
        with pytest.raises(KeyError, match="Notebook not found"):
            await manager.open_notebook(created.id)
    finally:
        await events.aclose()
