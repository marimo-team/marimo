# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
from unittest.mock import patch

from click.testing import CliRunner

from marimo._cli.agent import agent
from marimo._server.session_registry import SessionRegistryEntry
from marimo._utils.requests import Response

_ENTRIES_PATCH = (
    "marimo._server.session_registry.SessionRegistryReader.read_all"
)


def _make_entry(
    *,
    port: int = 2718,
    notebook_path: str | None = "notebook.py",
    pid: int | None = None,
) -> SessionRegistryEntry:
    return SessionRegistryEntry(
        server_id=f"localhost:{port}",
        pid=pid or os.getpid(),
        host="localhost",
        port=port,
        base_url="",
        auth_token="test-token",
        mode="edit",
        started_at="2026-01-01T00:00:00+00:00",
        notebook_path=notebook_path,
        mcp_enabled=False,
        version="0.0.0",
    )


def _mock_response(data: dict) -> Response:
    return Response(
        status_code=200,
        content=json.dumps(data).encode("utf-8"),
        headers={"content-type": "application/json"},
    )


# --- sessions list ---


def test_list_no_sessions():
    runner = CliRunner()
    with patch(_ENTRIES_PATCH, return_value=[]):
        result = runner.invoke(agent, ["sessions", "list"])
    assert result.exit_code == 0
    assert "No running marimo sessions found" in result.output


def test_list_table_output():
    runner = CliRunner()
    entries = [
        _make_entry(port=2718, notebook_path="analysis.py"),
        _make_entry(port=2719, notebook_path=None),
    ]
    with patch(_ENTRIES_PATCH, return_value=entries):
        result = runner.invoke(agent, ["sessions", "list"])
    assert result.exit_code == 0
    assert "SERVER" in result.output
    assert "localhost:2718" in result.output
    assert "analysis.py" in result.output
    assert "(multi/new)" in result.output


def test_list_json_output():
    runner = CliRunner()
    entry = _make_entry(port=2718)
    with patch(_ENTRIES_PATCH, return_value=[entry]):
        result = runner.invoke(agent, ["sessions", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["port"] == 2718
    assert "auth_token" not in data[0]


# --- exec ---


def test_exec_no_sessions():
    runner = CliRunner()
    with patch(_ENTRIES_PATCH, return_value=[]):
        result = runner.invoke(agent, ["exec", "-c", "print('hi')"])
    assert result.exit_code != 0
    assert "No running marimo sessions" in result.output


def test_exec_multiple_sessions_no_port():
    runner = CliRunner()
    entries = [_make_entry(port=2718), _make_entry(port=2719)]
    with patch(_ENTRIES_PATCH, return_value=entries):
        result = runner.invoke(agent, ["exec", "-c", "x"])
    assert result.exit_code != 0
    assert "Multiple running sessions" in result.output
    assert "--port" in result.output


def test_exec_successful():
    runner = CliRunner()
    entry = _make_entry(port=2718)
    mock_resp = _mock_response(
        {"success": True, "stdout": ["hello\n"], "output": None}
    )
    with (
        patch(_ENTRIES_PATCH, return_value=[entry]),
        patch(
            "marimo._cli.agent.exec_cmd._discover_session_id",
            return_value="sess-1",
        ),
        patch("marimo._utils.requests.post", return_value=mock_resp),
    ):
        result = runner.invoke(agent, ["exec", "-c", "print('hello')"])
    assert result.exit_code == 0
    assert "hello" in result.output


def test_exec_with_errors():
    runner = CliRunner()
    entry = _make_entry(port=2718)
    mock_resp = _mock_response(
        {
            "success": False,
            "errors": ["NameError: x is not defined"],
            "stdout": [],
        }
    )
    with (
        patch(_ENTRIES_PATCH, return_value=[entry]),
        patch(
            "marimo._cli.agent.exec_cmd._discover_session_id",
            return_value="sess-1",
        ),
        patch("marimo._utils.requests.post", return_value=mock_resp),
    ):
        result = runner.invoke(agent, ["exec", "-c", "print(x)"])
    assert result.exit_code != 0
    assert "NameError" in result.output
