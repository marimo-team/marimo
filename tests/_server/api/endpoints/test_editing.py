# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from marimo._dependencies.dependencies import DependencyManager
from tests._server.mocks import token_header, with_session

HAS_RUFF = DependencyManager.ruff.has()
HAS_FORMATTER = HAS_RUFF or DependencyManager.black.has()

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_code_autocomplete(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/code_autocomplete",
        headers=HEADERS,
        json={
            "id": "completion-123",
            "document": "print('Hello, World!')",
            "cellId": "cell-123",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_delete_cell(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/delete",
        headers=HEADERS,
        json={
            "cellId": "cell-123",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@pytest.mark.skipif(not HAS_FORMATTER, reason="ruff or black not installed")
@with_session(SESSION_ID)
def test_format_cell(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/format",
        headers=HEADERS,
        json={
            "codes": {
                "cell-123": "def foo():\n  return 1",
            },
            "lineLength": 80,
            "filename": None,
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    formatted_codes = response.json().get("codes", {})
    assert "cell-123" in formatted_codes
    assert formatted_codes["cell-123"] == "def foo():\n    return 1"


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_format_cell_with_filename(client: TestClient) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config = '[format]\nquote-style = "single"'
        tmp_path.joinpath("ruff.toml").write_text(config)
        response = client.post(
            "/api/kernel/format",
            headers=HEADERS,
            json={
                "codes": {"cell-123": 'x="1"'},
                "lineLength": 80,
                "filename": str(tmp_path / "notebook.py"),  # Added filename
            },
        )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    formatted_codes = response.json().get("codes", {})
    assert "cell-123" in formatted_codes
    assert formatted_codes["cell-123"] == "x = '1'"


def _fix_cell(client: TestClient, config: str, code: str) -> str | None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        config = f"[lint]\n{config}"
        tmp_path.joinpath("ruff.toml").write_text(config)
        response = client.post(
            "/api/kernel/fix",
            headers=HEADERS,
            json={
                "codes": {"cell-123": code},
                "lineLength": 80,
                "filename": str(tmp_path / "notebook.py"),
            },
        )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    return response.json().get("codes", {}).get("cell-123")


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_fix_cell_isort(client: TestClient) -> None:
    fixed_code = _fix_cell(client, 'select=["I"]', "import sys\nimport os")
    assert fixed_code == "import os\nimport sys"


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_fix_cell_pyflakes(client: TestClient) -> None:
    fixed_code = _fix_cell(client, 'select=["F"]', 'x=f"a"')
    assert fixed_code == 'x="a"'


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_fix_cell_flake8_bugbear(client: TestClient) -> None:
    fixed_code = _fix_cell(client, 'select=["B"]', "x={1,2,1}")
    assert fixed_code == "x={1,2}"


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_fix_cell_ignore_unused_import(client: TestClient) -> None:
    fixed_code = _fix_cell(client, 'select=["ALL"]', "import os")
    assert fixed_code == "import os"


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_fix_cell_ignore_required_imports(client: TestClient) -> None:
    config = 'select=["ALL"]\n[lint.isort]\nrequired-imports = ["import os"]'
    fixed_code = _fix_cell(client, config, "x=1")
    assert fixed_code == "x=1"


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_fix_cell_with_invalid_code(client: TestClient) -> None:
    fixed_code = _fix_cell(client, 'select=["ALL"]', "x=")
    assert fixed_code == "x="


@pytest.mark.skipif(not HAS_RUFF, reason="ruff not installed")
@with_session(SESSION_ID)
def test_fix_cell_with_invalid_ruff_config(client: TestClient) -> None:
    fixed_code = _fix_cell(client, 'select=["ALL"', "import os")
    assert fixed_code is None


@with_session(SESSION_ID)
def test_install_missing_packages(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/install_missing_packages",
        headers=HEADERS,
        json={
            "manager": "pip",
            "versions": {},
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_set_cell_config(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/set_cell_config",
        headers=HEADERS,
        json={
            "configs": {
                "cell-123": {"runnable": True},
            },
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_stdin(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/stdin",
        headers=HEADERS,
        json={
            "text": "user input",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()
