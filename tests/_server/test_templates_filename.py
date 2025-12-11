# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json

import pytest

from marimo._ast.app_config import _AppConfig
from marimo._config.config import MarimoConfig, PartialMarimoConfig
from marimo._server.templates.templates import (
    _get_mount_config,
    _html_escape,
    json_script,
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


class TestJsonScriptEscaping:
    """Test json_script() function for script tag breakout prevention."""

    @pytest.mark.parametrize(
        "payload",
        [
            # Script tag breakout attempts
            "</script><script>alert('XSS')</script>",
            "<script>alert(1)</script>",
            "</script><img src=x onerror=alert(1)>",
            "<img src=x onerror=alert(1)>",
            # JavaScript string breakout attempts
            "'; alert(1); //",
            '"; alert(1); //',
            # Raw script tags
            "</script>",
            "<script>",
            # Combinations
            ">&<",
            "</SCRIPT><SCRIPT>alert(1)</SCRIPT>",
            # With valid content mixed in
            "normal text</script><script>alert(1)</script>more text",
        ],
    )
    def test_script_breakout_prevention(self, payload: str) -> None:
        """Verify dangerous characters are escaped to prevent script tag breakout."""
        result = json_script({"malicious": payload})

        # Must not contain literal < or > that could break out of script tag
        # Note: json_script only escapes <, >, & - other strings are safe in JSON context
        assert "<script>" not in result.lower()
        assert "</script>" not in result.lower()

        # Must contain escaped versions of dangerous chars
        # json_script escapes <, >, & to \uXXXX format
        if "<" in payload or ">" in payload or "&" in payload:
            assert (
                "\\u003C" in result
                or "\\u003E" in result
                or "\\u0026" in result
            )

        # Must be valid JSON that round-trips correctly
        parsed = json.loads(result)
        assert parsed["malicious"] == payload

    @pytest.mark.parametrize(
        ("data", "must_not_contain"),
        [
            # Nested structures with malicious content
            (
                {"nested": {"deep": "</script><script>alert(1)</script>"}},
                ["</script>", "<script>"],
            ),
            # Arrays with malicious content
            (
                {"items": ["</script>", "<script>", "&"]},
                ["</script>", "<script>"],
            ),
            # Multiple fields with different injection attempts
            (
                {
                    "field1": "</script>",
                    "field2": "<img src=x onerror=alert(1)>",
                    "field3": "normal & text",
                },
                ["</script>", "<img"],
            ),
        ],
    )
    def test_complex_structure_escaping(
        self, data: dict, must_not_contain: list[str]
    ) -> None:
        """Verify json_script escapes dangerous chars in complex nested structures."""
        result = json_script(data)

        # Must not contain any unescaped dangerous sequences
        for dangerous in must_not_contain:
            assert dangerous not in result

        # Must be valid JSON that round-trips correctly
        parsed = json.loads(result)
        assert parsed == data

    @pytest.mark.parametrize(
        "data",
        [
            # Unicode characters
            {"text": "café"},
            {"text": "测试"},
            {"text": "🚀"},
            # Unicode mixed with dangerous characters
            {"text": "café</script>"},
            {"text": "测试<script>alert(1)</script>"},
            # Combining characters
            {"text": "e\u0301"},  # é as combining character
            # Right-to-left marks
            {"text": "\u200f"},
            # Zero-width characters
            {"text": "test\u200bword"},
        ],
    )
    def test_unicode_handling(self, data: dict) -> None:
        """Verify unicode characters are handled correctly without bypassing escaping."""
        result = json_script(data)

        # Must not contain unescaped dangerous sequences
        assert "</script>" not in result
        assert "<script>" not in result

        # Must be valid JSON that preserves unicode
        parsed = json.loads(result)
        assert parsed == data

    def test_json_validity_after_escaping(self) -> None:
        """Verify json_script produces valid JSON that JavaScript can parse."""
        test_data = {
            "string": "test</script>",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"key": "value<script>"},
        }

        result = json_script(test_data)

        # Must be valid JSON
        parsed = json.loads(result)
        assert parsed == test_data

        # Must maintain sort_keys=True behavior
        keys_order = list(parsed.keys())
        assert keys_order == sorted(keys_order)

    @pytest.mark.parametrize(
        "xss_payload",
        [
            # OWASP XSS cheat sheet payloads
            "<svg/onload=alert(1)>",
            "<iframe src=javascript:alert(1)>",
            "<object data=javascript:alert(1)>",
            "<embed src=javascript:alert(1)>",
            "<body onload=alert(1)>",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            # PortSwigger XSS payloads
            "<img src=x onerror=alert(document.domain)>",
            "<svg><script>alert(1)</script></svg>",
            # Encoded variations
            "</script><script>alert(String.fromCharCode(88,83,83))</script>",
            # Case variations
            "</ScRiPt><ScRiPt>alert(1)</ScRiPt>",
        ],
    )
    def test_real_world_xss_payloads(self, xss_payload: str) -> None:
        """Test json_script against real-world XSS attack payloads."""
        result = json_script({"payload": xss_payload})

        # Must not contain unescaped < or > that could break out of script tags
        # json_script specifically prevents script tag breakout by escaping <, >, &
        assert "<script" not in result.lower()

        # Must escape dangerous characters < and >
        if "<" in xss_payload or ">" in xss_payload:
            assert "\\u003C" in result or "\\u003E" in result

        # Must be valid JSON
        parsed = json.loads(result)
        assert parsed["payload"] == xss_payload


class TestMountConfigInjectionPrevention:
    """Test _get_mount_config prevents injection attacks in all fields."""

    @pytest.mark.parametrize(
        "malicious_filename",
        [
            "</script><script>alert('XSS')</script>.py",
            "<script>alert(1)</script>.py",
            "test</script>.py",
            "<img src=x onerror=alert(1)>.py",
        ],
    )
    def test_filename_injection_prevention(
        self, malicious_filename: str
    ) -> None:
        """Test that malicious filenames don't enable script breakout in mount config."""
        server_token = SkewProtectionToken("test-token")
        user_config = MarimoConfig()
        config_overrides = PartialMarimoConfig()
        app_config = _AppConfig()

        result = _get_mount_config(
            filename=malicious_filename,
            mode="edit",
            server_token=server_token,
            user_config=user_config,
            config_overrides=config_overrides,
            app_config=app_config,
        )

        # Remove trailing comma for JSON parsing
        last_comma_index = result.rfind(",")
        result = result[:last_comma_index] + result[last_comma_index + 1 :]

        # Must not contain unescaped script tags (< and > should be escaped)
        assert "</script><script>" not in result
        assert "<script>" not in result.lower()

        # Must be valid JSON
        config_data = json.loads(result)
        assert config_data["filename"] == malicious_filename

        # Verify the actual output contains escaped versions of < and >
        assert "\\u003C" in result or "\\u003E" in result

    @pytest.mark.parametrize(
        "malicious_title",
        [
            "</script><script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "normal title</script>",
        ],
    )
    def test_app_title_injection_prevention(
        self, malicious_title: str
    ) -> None:
        """Test that malicious app titles don't enable script breakout."""
        server_token = SkewProtectionToken("test-token")
        user_config = MarimoConfig()
        config_overrides = PartialMarimoConfig()
        app_config = _AppConfig(app_title=malicious_title)

        result = _get_mount_config(
            filename="test.py",
            mode="edit",
            server_token=server_token,
            user_config=user_config,
            config_overrides=config_overrides,
            app_config=app_config,
        )

        # Remove trailing comma
        last_comma_index = result.rfind(",")
        result = result[:last_comma_index] + result[last_comma_index + 1 :]

        # Must not contain unescaped script tags (< and > should be escaped)
        assert "</script><script>" not in result

        # Must be valid JSON
        config_data = json.loads(result)

        # Verify escaping in output (< and > are escaped)
        if "<" in malicious_title or ">" in malicious_title:
            assert "\\u003C" in result or "\\u003E" in result
