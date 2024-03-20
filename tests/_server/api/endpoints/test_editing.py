# Copyright 2024 Marimo. All rights reserved.


from starlette.testclient import TestClient

from tests._server.mocks import with_session

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    "Marimo-Server-Token": "fake-token",
}


@with_session(SESSION_ID)
def test_code_autocomplete(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/code_autocomplete",
        headers=HEADERS,
        json={
            "id": "completion-123",
            "document": "print('Hello, World!')",
            "cell_id": "cell-123",
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
            "cell_id": "cell-123",
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    assert "success" in response.json()


@with_session(SESSION_ID)
def test_format_cell(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/format",
        headers=HEADERS,
        json={
            "codes": {
                "cell-123": "def foo():\n  return 1",
            },
            "line_length": 80,
        },
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/json"
    formatted_codes = response.json().get("codes", {})
    assert "cell-123" in formatted_codes
    assert formatted_codes["cell-123"] == "def foo():\n    return 1"


@with_session(SESSION_ID)
def test_install_missing_packages(client: TestClient) -> None:
    response = client.post(
        "/api/kernel/install_missing_packages",
        headers=HEADERS,
        json={
            "manager": "pip",
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
