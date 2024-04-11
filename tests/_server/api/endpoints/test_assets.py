# Copyright 2024 Marimo. All rights reserved.
from tempfile import TemporaryDirectory
from typing import Any, cast

from starlette.testclient import TestClient

from marimo._server.api.utils import parse_title
from marimo._server.file_router import AppFileRouter
from marimo._server.sessions import SessionManager
from tests._server.mocks import with_file_router


def test_index(client: TestClient) -> None:
    session_manager: SessionManager = cast(
        Any, client.app
    ).state.session_manager
    response = client.get("/")
    assert response.status_code == 200, response.text
    content = response.text
    filename = session_manager.file_router.get_unique_file_key()
    title = parse_title(filename)
    assert f"<marimo-filename hidden>{filename}</marimo-filename>" in content
    assert filename is not None
    assert filename in content
    assert "<marimo-mode data-mode='edit'" in content
    assert f"<title>{title}</title>" in content
    assert session_manager.server_token in content


@with_file_router(AppFileRouter.from_files([]))
def test_index_when_empty(client: TestClient) -> None:
    session_manager: SessionManager = cast(
        Any, client.app
    ).state.session_manager
    response = client.get("/")
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert "<marimo-mode data-mode='home'" in content
    assert "<title>marimo</title>" in content
    assert session_manager.server_token in content


@with_file_router(AppFileRouter.new_file())
def test_index_when_new_file(client: TestClient) -> None:
    session_manager: SessionManager = cast(
        Any, client.app
    ).state.session_manager
    response = client.get("/")
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert "<marimo-mode data-mode='edit'" in content
    assert "<title>marimo</title>" in content
    assert session_manager.server_token in content


TEMP_DIR = TemporaryDirectory()


@with_file_router(AppFileRouter.from_directory(TEMP_DIR.name))
def test_index_with_directory(client: TestClient) -> None:
    session_manager: SessionManager = cast(
        Any, client.app
    ).state.session_manager
    response = client.get("/")
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename" in content
    assert "<marimo-mode data-mode='home'" in content
    assert "<title>marimo</title>" in content
    assert session_manager.server_token in content


def test_favicon(client: TestClient) -> None:
    response = client.get("/favicon.ico")
    assert response.status_code == 200, response.text
    content_type = response.headers["content-type"]
    assert (
        content_type == "image/x-icon"
        or content_type == "image/vnd.microsoft.icon"
    )


def test_unknown_file(client: TestClient) -> None:
    response = client.get("/unknown_file")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}
