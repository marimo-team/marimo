# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import MagicMock, patch

from marimo._messaging.tracebacks import (
    _highlight_traceback,
    is_code_highlighting,
    write_traceback,
)
from marimo._messaging.types import Stderr


class TestTracebacks:
    def test_highlight_traceback(self) -> None:
        # Test that _highlight_traceback adds HTML formatting
        traceback = "Traceback (most recent call last):\n  File \"<stdin>\", line 1, in <module>\nValueError: invalid value"

        highlighted = _highlight_traceback(traceback)

        # Should contain HTML formatting
        assert "<span class=\"codehilite\">" in highlighted
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
            traceback = "Traceback (most recent call last):\n  File \"<stdin>\", line 1, in <module>\nValueError: invalid value"
            write_traceback(traceback)

            # Should call _write_with_mimetype with highlighted traceback
            mock_stderr._write_with_mimetype.assert_called_once()

            # First argument should be the highlighted traceback
            args, _ = mock_stderr._write_with_mimetype.call_args
            assert "<span class=\"codehilite\">" in args[0]
            assert "Traceback" in args[0]

            # Second argument should be the mimetype
            _, kwargs = mock_stderr._write_with_mimetype.call_args
            assert kwargs["mimetype"] == "application/vnd.marimo+traceback"

    def test_write_traceback_to_regular_stderr(self) -> None:
        # Test writing traceback to regular stderr (not Stderr)
        mock_stderr = MagicMock()
        mock_stderr.write = MagicMock()

        with patch("sys.stderr", mock_stderr):
            traceback = "Traceback (most recent call last):\n  File \"<stdin>\", line 1, in <module>\nValueError: invalid value"
            write_traceback(traceback)

            # Should call write with the original traceback
            mock_stderr.write.assert_called_once_with(traceback)

    def test_is_code_highlighting(self) -> None:
        # Test is_code_highlighting function

        # Should return True for strings containing the codehilite class
        assert is_code_highlighting("<span class=\"codehilite\">code</span>") is True
        assert is_code_highlighting("before <span class=\"codehilite\">code</span> after") is True

        # Should return False for strings not containing the codehilite class
        assert is_code_highlighting("<span>code</span>") is False
        assert is_code_highlighting("") is False
        assert is_code_highlighting("class=\"not-codehilite\"") is False
