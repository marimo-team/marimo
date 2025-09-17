# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os

import pytest

from marimo._server.utils import canonicalize_filename


class TestCanonicalizeFilename:
    """Test filename canonicalization with unicode, spaces, and special characters."""

    @pytest.mark.parametrize(
        ("input_filename", "should_add_py"),
        [
            # Basic cases
            ("test", True),
            ("test.py", False),
            ("test.md", False),
            ("test.qmd", False),
            # Unicode characters
            ("tést", True),
            ("café.py", False),
            ("测试", True),
            ("🚀notebook.py", False),
            # Spaces
            ("test file", True),
            ("my notebook.py", False),
            # Mixed unicode and spaces
            ("café notebook", True),
            ("测试 file.py", False),
            # Special characters
            ("test-file", True),
            ("test_file.py", False),
            # Edge cases
            ("", True),
            (".", True),
            # User paths
            ("~/test", True),
            ("~/test.py", False),
            ("~/café notebook", True),
            ("~/测试 file.py", False),
        ],
    )
    def test_canonicalize_filename(
        self, input_filename: str, should_add_py: bool
    ) -> None:
        """Test that canonicalize_filename handles problematic filenames correctly."""
        result = canonicalize_filename(input_filename)

        # Should expand user path
        if should_add_py:
            expected = os.path.expanduser(input_filename + ".py")
        else:
            expected = os.path.expanduser(input_filename)

        assert result == expected

        # Should not contain ~ in the result if it was there
        if "~" in input_filename:
            assert "~" not in result

        # Result should be a valid string
        assert isinstance(result, str)
        assert len(result) > 0
