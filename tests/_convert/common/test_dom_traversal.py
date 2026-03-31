# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import patch

from marimo._convert.common.dom_traversal import (
    _is_virtual_file_url,
    _parse_virtual_file_url,
    replace_html_attributes,
    replace_virtual_files_with_data_uris,
)


class TestHTMLAttributeReplacer:
    def test_simple_replacement(self) -> None:
        """Test basic attribute replacement."""
        html = '<img src="test.png">'

        def upper_replacer(value: str) -> str:
            return value.upper()

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},
            allowed_attributes={"src"},
            replacer_fn=upper_replacer,
        )
        assert result == '<img src="TEST.PNG">'

    def test_multiple_tags(self) -> None:
        """Test replacement across multiple tags."""
        html = '<img src="test.png"><a href="link.html">Link</a>'

        def prefix_replacer(value: str) -> str:
            return f"prefix_{value}"

        result = replace_html_attributes(
            html,
            allowed_tags={"img", "a"},
            allowed_attributes={"src", "href"},
            replacer_fn=prefix_replacer,
        )
        assert (
            result
            == '<img src="prefix_test.png"><a href="prefix_link.html">Link</a>'
        )

    def test_selective_tag_replacement(self) -> None:
        """Test that only allowed tags are processed."""
        html = '<img src="test.png"><div data-src="other.png"></div>'

        def prefix_replacer(value: str) -> str:
            return f"prefix_{value}"

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},  # Only img, not div
            allowed_attributes={"src", "data-src"},
            replacer_fn=prefix_replacer,
        )
        # img src should be replaced, div data-src should not
        assert (
            result
            == '<img src="prefix_test.png"><div data-src="other.png"></div>'
        )

    def test_selective_attribute_replacement(self) -> None:
        """Test that only allowed attributes are processed."""
        html = '<img src="test.png" alt="description">'

        def prefix_replacer(value: str) -> str:
            return f"prefix_{value}"

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},
            allowed_attributes={"src"},  # Only src, not alt
            replacer_fn=prefix_replacer,
        )
        # src should be replaced, alt should not
        assert result == '<img src="prefix_test.png" alt="description">'

    def test_none_return_keeps_original(self) -> None:
        """Test that returning None from replacer keeps original value."""
        html = '<img src="test.png">'

        def conditional_replacer(value: str) -> str | None:
            if value == "test.png":
                return None  # Keep original
            return "replaced"

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},
            allowed_attributes={"src"},
            replacer_fn=conditional_replacer,
        )
        assert result == '<img src="test.png">'

    def test_self_closing_tags(self) -> None:
        """Test self-closing tags."""
        html = '<img src="test.png" />'

        def upper_replacer(value: str) -> str:
            return value.upper()

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},
            allowed_attributes={"src"},
            replacer_fn=upper_replacer,
        )
        assert result == '<img src="TEST.PNG" />'

    def test_preserves_other_content(self) -> None:
        """Test that text and other elements are preserved."""
        html = '<div>Text before<img src="test.png">Text after</div>'

        def upper_replacer(value: str) -> str:
            return value.upper()

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},
            allowed_attributes={"src"},
            replacer_fn=upper_replacer,
        )
        assert result == '<div>Text before<img src="TEST.PNG">Text after</div>'

    def test_complex_html(self) -> None:
        """Test with more complex HTML structure."""
        html = """
        <div class="container">
            <img src="image1.png" alt="First" />
            <a href="link.html">Click here</a>
            <img src="image2.png" />
        </div>
        """

        def prefix_replacer(value: str) -> str:
            return f"https://cdn.example.com/{value}"

        result = replace_html_attributes(
            html,
            allowed_tags={"img", "a"},
            allowed_attributes={"src", "href"},
            replacer_fn=prefix_replacer,
        )

        assert 'src="https://cdn.example.com/image1.png"' in result
        assert 'src="https://cdn.example.com/image2.png"' in result
        assert 'href="https://cdn.example.com/link.html"' in result

    def test_quoted_attributes(self) -> None:
        """Test that quotes in values are properly escaped."""
        html = '<img src="test.png">'

        def quote_replacer(value: str) -> str:
            del value
            return 'value with "quotes"'

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},
            allowed_attributes={"src"},
            replacer_fn=quote_replacer,
        )
        # Quotes should be escaped
        assert 'src="value with &quot;quotes&quot;"' in result


class TestVirtualFilePatterns:
    def test_is_virtual_file_url(self) -> None:
        """Test virtual file URL detection."""
        assert _is_virtual_file_url("./@file/29676-test.png") is True
        assert _is_virtual_file_url("./@file/123-file.jpg") is True
        assert _is_virtual_file_url("https://example.com/image.png") is False
        assert _is_virtual_file_url("./regular-file.png") is False
        assert (
            _is_virtual_file_url("@file/123-test.png") is False
        )  # Missing ./

    def test_parse_virtual_file_url(self) -> None:
        """Test virtual file URL parsing."""
        result = _parse_virtual_file_url("./@file/29676-test.png")
        assert result == (29676, "test.png")

        result = _parse_virtual_file_url("./@file/123-complex-file-name.jpg")
        assert result == (123, "complex-file-name.jpg")

        result = _parse_virtual_file_url("https://example.com/image.png")
        assert result is None

    def test_parse_virtual_file_with_hyphens(self) -> None:
        """Test parsing virtual files with hyphens in filename."""
        result = _parse_virtual_file_url("./@file/29676-25241121-ZSE6dgpj.png")
        assert result == (29676, "25241121-ZSE6dgpj.png")


class TestVirtualFileReplacement:
    def test_conditional_replacement(self) -> None:
        """Test that only virtual files are replaced."""
        html = """
        <img src="./@file/123-test.png">
        <img src="https://example.com/image.png">
        <img src="./regular.png">
        """

        def replacer(value: str) -> str | None:
            if _is_virtual_file_url(value):
                return "data:image/png;base64,MOCK_DATA"
            return None

        result = replace_html_attributes(
            html,
            allowed_tags={"img"},
            allowed_attributes={"src"},
            replacer_fn=replacer,
        )

        # Virtual file should be replaced
        assert 'src="data:image/png;base64,MOCK_DATA"' in result
        # Regular URLs should remain unchanged
        assert 'src="https://example.com/image.png"' in result
        assert 'src="./regular.png"' in result

    def test_audio_and_video_tags_replaced(self) -> None:
        """Test that audio and video virtual files are replaced."""
        html = (
            '<audio src="./@file/500-clip.wav" controls></audio>'
            '<video src="./@file/600-movie.mp4"></video>'
            '<img src="./@file/100-pic.png">'
        )

        with patch(
            "marimo._convert.common.dom_traversal.read_virtual_file"
        ) as mock_read:
            mock_read.return_value = b"fake_data"

            result, replaced = replace_virtual_files_with_data_uris(
                html, allowed_tags={"img", "audio", "video"}
            )

        assert "./@file/500-clip.wav" not in result
        assert "./@file/600-movie.mp4" not in result
        assert "./@file/100-pic.png" not in result
        # mimetypes returns audio/x-wav on macOS/Linux, audio/wav on Windows
        assert (
            "data:audio/x-wav;base64," in result
            or "data:audio/wav;base64," in result
        )
        assert "data:video/mp4;base64," in result
        assert "data:image/png;base64," in result
        assert len(replaced) == 3

    def test_max_inline_bytes_skips_large_files(self) -> None:
        """Test that files exceeding max_inline_bytes are not inlined."""
        html = (
            '<audio src="./@file/1000-small.wav" controls></audio>'
            '<audio src="./@file/9999999-large.wav" controls></audio>'
        )

        with patch(
            "marimo._convert.common.dom_traversal.read_virtual_file"
        ) as mock_read:
            mock_read.return_value = b"audio_data"

            result, replaced = replace_virtual_files_with_data_uris(
                html,
                allowed_tags={"audio"},
                max_inline_bytes=5_000_000,
            )

        # Small file should be inlined
        assert "./@file/1000-small.wav" not in result
        # mimetypes returns audio/x-wav on macOS/Linux, audio/wav on Windows
        assert (
            "data:audio/x-wav;base64," in result
            or "data:audio/wav;base64," in result
        )
        assert "./@file/1000-small.wav" in replaced

        # Large file should get a text/plain placeholder instead of the
        # original (unresolvable) ./@file/ URL
        assert "./@file/9999999-large.wav" not in result
        assert "data:text/plain;base64," in result
        assert "./@file/9999999-large.wav" not in replaced
