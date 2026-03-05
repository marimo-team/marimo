# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from marimo._cli.session import session
from marimo._server.session_registry import SessionRegistryEntry


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


_ENTRIES_PATCH = (
    "marimo._server.session_registry.SessionRegistryReader.read_all"
)


class TestListCommand:
    def test_no_sessions(self) -> None:
        runner = CliRunner()
        with patch(_ENTRIES_PATCH, return_value=[]):
            result = runner.invoke(session, ["list"])
        assert result.exit_code == 0
        assert "No running marimo sessions found" in result.output

    def test_table_output(self) -> None:
        runner = CliRunner()
        entry = _make_entry(port=2718, notebook_path="analysis.py")
        with patch(_ENTRIES_PATCH, return_value=[entry]):
            result = runner.invoke(session, ["list"])
        assert result.exit_code == 0
        assert "localhost:2718" in result.output
        assert "analysis.py" in result.output
        assert "edit" in result.output
        assert "SERVER" in result.output  # header

    def test_json_output(self) -> None:
        runner = CliRunner()
        entry = _make_entry(port=2718)
        with patch(_ENTRIES_PATCH, return_value=[entry]):
            result = runner.invoke(session, ["list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["port"] == 2718
        # Auth token should be redacted
        assert "auth_token" not in data[0]

    def test_null_notebook_path(self) -> None:
        runner = CliRunner()
        entry = _make_entry(notebook_path=None)
        with patch(_ENTRIES_PATCH, return_value=[entry]):
            result = runner.invoke(session, ["list"])
        assert result.exit_code == 0
        assert "(multi/new)" in result.output


class TestExecCommand:
    def test_no_sessions_exits(self) -> None:
        runner = CliRunner()
        with patch(_ENTRIES_PATCH, return_value=[]):
            result = runner.invoke(session, ["exec", "-c", "print('hi')"])
        assert result.exit_code != 0
        assert "No running marimo sessions" in result.output

    def test_multiple_sessions_no_port(self) -> None:
        runner = CliRunner()
        entries = [_make_entry(port=2718), _make_entry(port=2719)]
        with patch(_ENTRIES_PATCH, return_value=entries):
            result = runner.invoke(session, ["exec", "-c", "x"])
        assert result.exit_code != 0
        assert "Multiple running sessions" in result.output
        assert "--port" in result.output

    def test_port_not_found(self) -> None:
        runner = CliRunner()
        with patch(_ENTRIES_PATCH, return_value=[_make_entry(port=2718)]):
            result = runner.invoke(
                session, ["exec", "-c", "x", "--port", "9999"]
            )
        assert result.exit_code != 0
        assert "9999" in result.output

    def test_successful_exec(self) -> None:
        runner = CliRunner()
        entry = _make_entry(port=2718)
        mock_resp = _mock_response(
            {"success": True, "stdout": ["hello\n"], "output": None}
        )
        with (
            patch(_ENTRIES_PATCH, return_value=[entry]),
            patch(
                "marimo._cli.session.exec_cmd._discover_session_id",
                return_value="sess-1",
            ),
            patch(
                "marimo._utils.requests.post",
                return_value=mock_resp,
            ),
        ):
            result = runner.invoke(session, ["exec", "-c", "print('hello')"])
        assert result.exit_code == 0
        assert "hello" in result.output

    def test_exec_with_errors(self) -> None:
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
                "marimo._cli.session.exec_cmd._discover_session_id",
                return_value="sess-1",
            ),
            patch(
                "marimo._utils.requests.post",
                return_value=mock_resp,
            ),
        ):
            result = runner.invoke(session, ["exec", "-c", "print(x)"])
        assert result.exit_code != 0
        assert "NameError" in result.output

    def test_exec_with_explicit_id(self) -> None:
        """When --id is passed, session discovery is skipped."""
        runner = CliRunner()
        entry = _make_entry(port=2718)
        mock_resp = _mock_response({"success": True, "stdout": ["ok\n"]})
        with (
            patch(_ENTRIES_PATCH, return_value=[entry]),
            patch(
                "marimo._utils.requests.post",
                return_value=mock_resp,
            ) as mock_post,
        ):
            result = runner.invoke(
                session, ["exec", "-c", "1+1", "--id", "my-session"]
            )
        assert result.exit_code == 0
        # Verify session ID was passed in headers
        call_kwargs = mock_post.call_args
        assert (
            call_kwargs.kwargs["headers"]["Marimo-Session-Id"] == "my-session"
        )

    def test_exec_connection_error(self) -> None:
        runner = CliRunner()
        entry = _make_entry(port=2718)
        from marimo._utils.requests import RequestError

        with (
            patch(_ENTRIES_PATCH, return_value=[entry]),
            patch(
                "marimo._cli.session.exec_cmd._discover_session_id",
                return_value="sess-1",
            ),
            patch(
                "marimo._utils.requests.post",
                side_effect=RequestError("Connection refused"),
            ),
        ):
            result = runner.invoke(session, ["exec", "-c", "x"])
        assert result.exit_code != 0
        assert "Connection refused" in result.output


class TestDiscoverSessionId:
    def test_single_session(self) -> None:
        from marimo._cli.session.exec_cmd import _discover_session_id

        entry = _make_entry()
        mock_resp = _mock_response(
            {"sess-1": {"filename": "nb.py", "path": "/nb.py"}}
        )
        with patch("marimo._utils.requests.get", return_value=mock_resp):
            sid = _discover_session_id(entry)
        assert sid == "sess-1"

    def test_multiple_sessions_exits(self) -> None:
        from marimo._cli.session.exec_cmd import _discover_session_id

        entry = _make_entry()
        mock_resp = _mock_response(
            {
                "sess-1": {"filename": "a.py"},
                "sess-2": {"filename": "b.py"},
            }
        )
        with (
            patch("marimo._utils.requests.get", return_value=mock_resp),
            pytest.raises(SystemExit),
        ):
            _discover_session_id(entry)

    def test_empty_response(self) -> None:
        from marimo._cli.session.exec_cmd import _discover_session_id

        entry = _make_entry()
        mock_resp = _mock_response({})
        with patch("marimo._utils.requests.get", return_value=mock_resp):
            sid = _discover_session_id(entry)
        assert sid is None

    def test_request_error(self) -> None:
        from marimo._cli.session.exec_cmd import _discover_session_id
        from marimo._utils.requests import RequestError

        entry = _make_entry()
        with patch(
            "marimo._utils.requests.get",
            side_effect=RequestError("timeout"),
        ):
            sid = _discover_session_id(entry)
        assert sid is None


def _mock_response(data: dict) -> object:
    """Create a mock Response that behaves like marimo._utils.requests.Response."""
    from marimo._utils.requests import Response

    content = json.dumps(data).encode("utf-8")
    return Response(
        status_code=200,
        content=content,
        headers={"content-type": "application/json"},
    )
