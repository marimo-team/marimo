# Copyright 2024 Marimo. All rights reserved.
from starlette.testclient import TestClient

from tests._server.mocks import token_header, with_session

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_snippets(client: TestClient) -> None:
    response = client.get("/api/documentation/snippets", headers=HEADERS)
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["snippets"] is not None
    assert len(content["snippets"]) > 0
    snippets = content["snippets"]

    # call the endpoint a second time and make sure the
    # same snippets are retrieved
    response = client.get("/api/documentation/snippets", headers=HEADERS)
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["snippets"] is not None
    assert len(content["snippets"]) > 0
    assert content["snippets"] == snippets
