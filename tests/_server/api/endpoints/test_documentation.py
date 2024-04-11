# Copyright 2024 Marimo. All rights reserved.
from starlette.testclient import TestClient


def test_snippets(client: TestClient) -> None:
    response = client.get("/api/documentation/snippets")
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["snippets"] is not None
    assert len(content["snippets"]) > 0
    snippets = content["snippets"]

    # call the endpoint a second time and make sure the
    # same snippets are retrieved
    response = client.get("/api/documentation/snippets")
    assert response.status_code == 200, response.text
    content = response.json()
    assert content["snippets"] is not None
    assert len(content["snippets"]) > 0
    assert content["snippets"] == snippets
