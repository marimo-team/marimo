# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from marimo._messaging.context import HTTP_REQUEST_CTX, is_code_mode_request
from marimo._messaging.tracebacks import (
    _highlight_traceback,
    format_exception_message,
    is_code_highlighting,
    write_traceback,
)
from marimo._messaging.types import Stderr
from marimo._runtime.commands import HTTPRequest


class TestTracebacks:
    def test_highlight_traceback(self) -> None:
        # Test that _highlight_traceback adds HTML formatting
        traceback = 'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nValueError: invalid value'

        highlighted = _highlight_traceback(traceback)

        # Should contain HTML formatting
        assert '<span class="codehilite">' in highlighted
        assert "</span>" in highlighted

        # Should contain the original traceback text
        assert "Traceback" in highlighted
        # The ValueError text is present but with HTML tags around it
        assert "ValueError" in highlighted
        assert "invalid value" in highlighted

    def test_write_traceback_to_stderr(self) -> None:
        # Test writing traceback to Stderr
        mock_stderr = MagicMock(spec=Stderr)

        with patch("sys.stderr", mock_stderr):
            traceback = 'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nValueError: invalid value'
            write_traceback(traceback)

            # Should call _write_with_mimetype with highlighted traceback
            mock_stderr._write_with_mimetype.assert_called_once()

            # First argument should be the highlighted traceback
            args, _ = mock_stderr._write_with_mimetype.call_args
            assert '<span class="codehilite">' in args[0]
            assert "Traceback" in args[0]

            # Second argument should be the mimetype
            _, kwargs = mock_stderr._write_with_mimetype.call_args
            assert kwargs["mimetype"] == "application/vnd.marimo+traceback"

    def test_write_traceback_to_regular_stderr(self) -> None:
        # Test writing traceback to regular stderr (not Stderr)
        mock_stderr = MagicMock()
        mock_stderr.write = MagicMock()

        with patch("sys.stderr", mock_stderr):
            traceback = 'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nValueError: invalid value'
            write_traceback(traceback)

            # Should call write with the original traceback
            mock_stderr.write.assert_called_once_with(traceback)

    def test_is_code_highlighting(self) -> None:
        # Test is_code_highlighting function

        # Should return True for strings containing the codehilite class
        assert (
            is_code_highlighting('<span class="codehilite">code</span>')
            is True
        )
        assert (
            is_code_highlighting(
                'before <span class="codehilite">code</span> after'
            )
            is True
        )

        # Should return False for strings not containing the codehilite class
        assert is_code_highlighting("<span>code</span>") is False
        assert is_code_highlighting("") is False
        assert is_code_highlighting('class="not-codehilite"') is False

    def test_write_traceback_plain_text_in_code_mode(self) -> None:
        """When request is from /api/kernel/execute, use plain text."""
        mock_stderr = MagicMock(spec=Stderr)
        req = HTTPRequest(
            url={"path": "/api/kernel/execute"},
            base_url={},
            headers={},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )
        token = HTTP_REQUEST_CTX.set(req)
        try:
            with patch("sys.stderr", mock_stderr):
                traceback = 'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nValueError: bad'
                write_traceback(traceback)
                mock_stderr.write.assert_called_once()
                mock_stderr._write_with_mimetype.assert_not_called()
        finally:
            HTTP_REQUEST_CTX.reset(token)

    def test_write_traceback_html_for_regular_http_request(self) -> None:
        """Regular HTTP requests (no code-mode header) get HTML tracebacks."""
        mock_stderr = MagicMock(spec=Stderr)
        req = HTTPRequest(
            url={},
            base_url={},
            headers={"accept": "application/json"},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )
        token = HTTP_REQUEST_CTX.set(req)
        try:
            with patch("sys.stderr", mock_stderr):
                traceback = 'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nValueError: bad'
                write_traceback(traceback)
                mock_stderr._write_with_mimetype.assert_called_once()
                mock_stderr.write.assert_not_called()
        finally:
            HTTP_REQUEST_CTX.reset(token)

    def test_write_traceback_suppressed_in_run_mode(self) -> None:
        """In run mode with show_tracebacks=False, nothing is sent to the frontend."""
        mock_stderr = MagicMock(spec=Stderr)
        with (
            patch("sys.stderr", mock_stderr),
            patch("marimo._messaging.tracebacks.get_mode", return_value="run"),
            patch(
                "marimo._messaging.tracebacks._show_tracebacks_enabled",
                return_value=False,
            ),
        ):
            write_traceback(
                'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nRuntimeError: secret'
            )
            mock_stderr._write_with_mimetype.assert_not_called()
            mock_stderr.write.assert_not_called()

    def test_write_traceback_forwarded_in_run_mode_with_show_tracebacks(
        self,
    ) -> None:
        """In run mode with show_tracebacks=True, traceback is sent to the frontend."""
        mock_stderr = MagicMock(spec=Stderr)
        with (
            patch("sys.stderr", mock_stderr),
            patch("marimo._messaging.tracebacks.get_mode", return_value="run"),
            patch(
                "marimo._messaging.tracebacks._show_tracebacks_enabled",
                return_value=True,
            ),
        ):
            write_traceback(
                'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nRuntimeError: visible'
            )
            mock_stderr._write_with_mimetype.assert_called_once()
            _, kwargs = mock_stderr._write_with_mimetype.call_args
            assert kwargs["mimetype"] == "application/vnd.marimo+traceback"


class TestFormatExceptionMessage:
    def test_name_error_includes_suggestion(self) -> None:
        """Python's "Did you mean: ..." suggestion is kept (str() drops it)."""
        aaa = 1
        with pytest.raises(NameError) as excinfo:
            print(aa)  # type: ignore[name-defined]  # noqa: F821
        msg = format_exception_message(excinfo.value)
        # The base message is stable across all supported Python versions.
        assert msg.startswith("name 'aa' is not defined")
        # Python 3.13 was the first release where `TracebackException` exposes
        # the "Did you mean: ..." hint via `format_exception_only`; on 3.10-
        # 3.12 the interpreter prints the hint in C but doesn't surface it
        # there, so the helper degrades to the base message on those versions.
        if sys.version_info >= (3, 13):
            assert "Did you mean: 'aaa'?" in msg

    def test_plain_message_unchanged(self) -> None:
        """Without a suggestion, the bare message is returned without the
        leading "ExceptionType: " prefix."""
        with pytest.raises(ValueError) as excinfo:
            raise ValueError("some message")
        assert format_exception_message(excinfo.value) == "some message"

    def test_empty_message(self) -> None:
        with pytest.raises(RuntimeError) as excinfo:
            raise RuntimeError
        assert format_exception_message(excinfo.value) == ""

    def test_message_containing_colon(self) -> None:
        with pytest.raises(ValueError) as excinfo:
            raise ValueError("expected: a value")
        assert format_exception_message(excinfo.value) == "expected: a value"


class TestIsCodeModeRequest:
    def test_no_request_context(self) -> None:
        assert is_code_mode_request() is False

    def test_execute_endpoint(self) -> None:
        req = HTTPRequest(
            url={"path": "/api/kernel/execute"},
            base_url={},
            headers={},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )
        token = HTTP_REQUEST_CTX.set(req)
        try:
            assert is_code_mode_request() is True
        finally:
            HTTP_REQUEST_CTX.reset(token)

    def test_run_endpoint(self) -> None:
        req = HTTPRequest(
            url={"path": "/api/kernel/run"},
            base_url={},
            headers={},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )
        token = HTTP_REQUEST_CTX.set(req)
        try:
            assert is_code_mode_request() is False
        finally:
            HTTP_REQUEST_CTX.reset(token)

    def test_empty_url(self) -> None:
        req = HTTPRequest(
            url={},
            base_url={},
            headers={},
            query_params={},
            path_params={},
            cookies={},
            meta={},
            user=None,
        )
        token = HTTP_REQUEST_CTX.set(req)
        try:
            assert is_code_mode_request() is False
        finally:
            HTTP_REQUEST_CTX.reset(token)
