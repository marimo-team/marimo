# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

from tests._server.mocks import token_header, with_read_session, with_session

if TYPE_CHECKING:
    from starlette.testclient import TestClient

SESSION_ID = "session-123"
HEADERS = {
    "Marimo-Session-Id": SESSION_ID,
    **token_header("fake-token"),
}


@with_session(SESSION_ID)
def test_invoke_tool(client: TestClient) -> None:
    response = client.post(
        "/api/ai/invoke_tool",
        headers=HEADERS,
        json={"tool_name": "test_tool", "arguments": {}},
    )
    assert response.status_code == 200
    assert response.json() == {
        "error": "Tool 'test_tool' not found. Available tools: ",
        "result": None,
        "success": False,
        "tool_name": "test_tool",
    }


@with_read_session(SESSION_ID)
def test_invoke_tool_fails_read_mode(client: TestClient) -> None:
    """Test that the endpoint requires edit permissions."""
    response = client.post(
        "/api/ai/invoke_tool",
        headers=HEADERS,
        json={"tool_name": "test_tool", "arguments": {}},
    )
    assert response.status_code == 401


@with_session(SESSION_ID)
def test_invoke_tool_with_arguments(client: TestClient) -> None:
    """Test that the endpoint handles argument params."""
    complex_args = {
        "string_param": "test_value",
        "number_param": 42,
        "boolean_param": True,
        "array_param": [1, 2, 3],
        "object_param": {"nested": "value"},
        "null_param": None,
    }

    response = client.post(
        "/api/ai/invoke_tool",
        headers=HEADERS,
        json={"tool_name": "test_tool", "arguments": complex_args},
    )
    assert response.status_code == 200
    assert response.json() == {
        "error": "Tool 'test_tool' not found. Available tools: ",
        "result": None,
        "success": False,
        "tool_name": "test_tool",
    }
