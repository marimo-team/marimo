# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json

import pytest

from marimo._ast.app_config import _AppConfig
from marimo._config.config import MarimoConfig, PartialMarimoConfig
from marimo._server.templates.templates import (
    _get_mount_config,
    _html_escape,
)
from marimo._server.tokens import SkewProtectionToken
from tests.mocks import EDGE_CASE_FILENAMES


class TestTemplateFilenameHandling:
    """Test template filename handling with unicode, spaces, and special characters."""

    @pytest.mark.parametrize(
        ("filename", "expected_contains"),
        [
            # Basic cases
            ("test.py", "test.py"),
            # HTML special characters that need escaping
            ("<script>alert('xss')</script>.py", "&lt;script&gt;"),
            ("test&example.py", "&amp;"),
            ('test"quotes".py', "&quot;"),
            ("test'quotes'.py", "&#x27;"),
            # Unicode characters (should be preserved)
            ("tést.py", "tést.py"),
            ("café.py", "café.py"),
            ("测试.py", "测试.py"),
            ("🚀notebook.py", "🚀notebook.py"),
            # Spaces (should be preserved)
            ("test file.py", "test file.py"),
            ("my notebook.py", "my notebook.py"),
            # Mixed unicode and spaces
            ("café notebook.py", "café notebook.py"),
            ("测试 file.py", "测试 file.py"),
            # Complex injection attempts
            ("test<>&'\"file.py", "&lt;&gt;&amp;&#x27;&quot;"),
        ],
    )
    def test_html_escape_function(
        self, filename: str, expected_contains: str
    ) -> None:
        """Test _html_escape function properly escapes HTML while preserving unicode."""
        result = _html_escape(filename)
        assert expected_contains in result

        # Should not contain unescaped HTML
        assert "<script>" not in result
        assert "onerror=" not in result

    @pytest.mark.parametrize(
        "filename",
        [*EDGE_CASE_FILENAMES, None],
    )
    def test_get_mount_config_filename_handling(
        self, filename: str | None
    ) -> None:
        """Test _get_mount_config function with problematic filenames."""
        server_token = SkewProtectionToken("test-token")
        user_config = MarimoConfig()
        config_overrides = PartialMarimoConfig()
        app_config = _AppConfig()

        result = _get_mount_config(
            filename=filename,
            mode="edit",
            server_token=server_token,
            user_config=user_config,
            config_overrides=config_overrides,
            app_config=app_config,
        )
        # Remove the last ','
        last_comma_index = result.rfind(",")
        result = result[:last_comma_index] + result[last_comma_index + 1 :]

        # Should be valid JSON
        config_data = json.loads(result)

        # Filename should be properly handled
        expected_filename = filename or ""
        assert config_data["filename"] == expected_filename
