# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, cast

from marimo._server.api.deps import AppState
from marimo._server.api.utils import parse_title
from marimo._server.file_router import AppFileRouter
from tests._server.mocks import token_header, with_file_router

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def test_index(client: TestClient) -> None:
    session_manager = AppState.from_app(cast(Any, client.app)).session_manager

    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    filename = session_manager.file_router.get_unique_file_key()
    title = parse_title(filename)
    assert f"<marimo-filename hidden>{filename}</marimo-filename>" in content
    assert filename is not None
    assert filename in content
    assert "<marimo-mode data-mode='edit'" in content
    assert f"<title>{title}</title>" in content


def test_custom_css_empty(client: TestClient) -> None:
    response = client.get("/custom.css", headers=token_header())
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/css; charset=utf-8"


def test_custom_css_non_empty(client: TestClient) -> None:
    session_manager = AppState.from_app(cast(Any, client.app)).session_manager
    css = "/* custom css */"
    filename = session_manager.file_router.get_unique_file_key()
    assert filename is not None

    css_file = os.path.join(os.path.dirname(filename), "custom.css")
    with open(css_file, "w") as f:
        f.write(css)

    # set config
    session_manager.app_manager(filename).save_app_config(
        {"css_file": "custom.css"}
    )

    try:
        response = client.get("/custom.css", headers=token_header())
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "text/css; charset=utf-8"
        assert response.text == css
    finally:
        os.remove(css_file)


@with_file_router(AppFileRouter.from_files([]))
def test_index_when_empty(client: TestClient) -> None:
    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert "<marimo-mode data-mode='home'" in content
    assert "<title>marimo</title>" in content


@with_file_router(AppFileRouter.new_file())
def test_index_when_new_file(client: TestClient) -> None:
    # Login page
    response = client.get("/")  # no header
    assert response.status_code == 200, response.text
    assert "Login" in response.text
    assert "marimo-filename" not in response.text

    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename hidden></marimo-filename>" in content
    assert "<marimo-mode data-mode='edit'" in content
    assert "<title>marimo</title>" in content


TEMP_DIR = TemporaryDirectory()


@with_file_router(AppFileRouter.from_directory(TEMP_DIR.name))
def test_index_with_directory(client: TestClient) -> None:
    response = client.get("/", headers=token_header())
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename" in content
    assert "<marimo-mode data-mode='home'" in content
    assert "<title>marimo</title>" in content


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


def test_vfile(client: TestClient) -> None:
    response = client.get("/@file/example.txt")
    assert response.status_code == 401, response.text

    response = client.get("/@file/empty.txt", headers=token_header())
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.content == b""

    response = client.get("/@file/bad.txt", headers=token_header())
    assert response.status_code == 404, response.text
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Invalid virtual file request"}
