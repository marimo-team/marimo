from fastapi.testclient import TestClient

from marimo._server2.api.deps import get_session_manager_state
from marimo._server2.main import app
from marimo._server2.tests.mocks import MOCK_MANAGER_STATE

app.dependency_overrides[
    get_session_manager_state
] = lambda: MOCK_MANAGER_STATE


def test_index(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    content = response.text
    assert "<marimo-filename" in content
    assert MOCK_MANAGER_STATE.filename is not None
    assert MOCK_MANAGER_STATE.filename in content
    assert "read" in content
    assert MOCK_MANAGER_STATE.server_token in content


def test_favicon(client: TestClient) -> None:
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/x-icon"


def test_unknown_file(client: TestClient) -> None:
    response = client.get("/unknown_file")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}
