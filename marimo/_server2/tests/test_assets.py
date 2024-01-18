from fastapi.testclient import TestClient

from marimo._server.sessions import get_manager
from marimo._server2.api.deps import get_session_manager_state
from marimo._server2.main import app
from marimo._server2.tests.mocks import (
    get_mock_session_manager,
)

app.dependency_overrides[get_manager] = get_mock_session_manager


def test_index(client: TestClient) -> None:
    state = get_session_manager_state(get_mock_session_manager())
    response = client.get("/")
    assert response.status_code == 200, response.text
    content = response.text
    assert "<marimo-filename" in content
    assert state.filename is not None
    assert state.filename in content
    assert "edit" in content
    assert state.server_token in content


def test_favicon(client: TestClient) -> None:
    response = client.get("/favicon.ico")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/x-icon"


def test_unknown_file(client: TestClient) -> None:
    response = client.get("/unknown_file")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}
