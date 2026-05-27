# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import TYPE_CHECKING
from unittest.mock import patch

if TYPE_CHECKING:
    from pathlib import Path

from marimo._convert.common.dom_traversal import (
    _is_virtual_file_url,
    _parse_virtual_file_url,
    replace_html_attributes,
    replace_public_files_with_data_uris,
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


class TestPublicFileReplacement:
    def test_inlines_public_image(self, tmp_path: Path) -> None:
        """Test that public/ image references are inlined as data URIs."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        data = b"\x89PNG\r\n\x1a\nfake"
        (public_dir / "image.png").write_bytes(data)

        html = '<img src="public/image.png">'

        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert 'src="public/image.png"' not in result
        assert "data:image/png;base64," in result
        assert base64.b64encode(data).decode() in result
        assert replaced == {"public/image.png"}

    def test_inlines_dot_slash_public_image(self, tmp_path: Path) -> None:
        """Test that ./public/ prefix is also inlined."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (public_dir / "image.png").write_bytes(b"data")

        html = '<img src="./public/image.png">'

        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert "data:image/png;base64," in result
        assert replaced == {"./public/image.png"}

    def test_inlines_nested_public_file(self, tmp_path: Path) -> None:
        """Test that nested files under public/ work."""
        public_dir = tmp_path / "public"
        (public_dir / "imgs").mkdir(parents=True)
        (public_dir / "imgs" / "logo.svg").write_bytes(b"<svg/>")

        html = '<img src="public/imgs/logo.svg">'

        result, _ = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert "data:image/svg+xml;base64," in result

    def test_blocks_path_traversal(self, tmp_path: Path) -> None:
        """Test that path traversal escaping public/ is rejected."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (tmp_path / "secret.txt").write_bytes(b"shh")

        html = '<img src="public/../secret.txt">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        # Original src is preserved; secret is not inlined.
        assert base64.b64encode(b"shh").decode() not in result
        assert replaced == set()

    def test_ignores_external_urls(self, tmp_path: Path) -> None:
        """Test that http(s) URLs are not touched."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()

        html = '<img src="https://example.com/img.png">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert result == html
        assert replaced == set()

    def test_ignores_other_relative_paths(self, tmp_path: Path) -> None:
        """Test that non-public relative paths are not touched."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (tmp_path / "other.png").write_bytes(b"data")

        html = '<img src="other.png">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert result == html
        assert replaced == set()

    def test_missing_file_left_unchanged(self, tmp_path: Path) -> None:
        """Test that references to missing files are kept as-is."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()

        html = '<img src="public/missing.png">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert 'src="public/missing.png"' in result
        assert replaced == set()

    def test_max_inline_bytes_skips_large_file(self, tmp_path: Path) -> None:
        """Test that files exceeding max_inline_bytes are skipped."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (public_dir / "big.png").write_bytes(b"x" * 1000)

        html = '<img src="public/big.png">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir, max_inline_bytes=100
        )

        # Large file is not inlined as image; original src is preserved.
        assert "data:image/png;base64," not in result
        assert 'src="public/big.png"' in result
        assert replaced == set()

    def test_audio_and_video_tags(self, tmp_path: Path) -> None:
        """Test that audio and video public references are inlined too."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (public_dir / "clip.mp4").write_bytes(b"video_data")

        html = '<video src="public/clip.mp4"></video>'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert "data:video/mp4;base64," in result
        assert replaced == {"public/clip.mp4"}

    def test_no_public_dir(self, tmp_path: Path) -> None:
        """Test that a missing public directory yields no-op."""
        public_dir = tmp_path / "public"
        # Note: do not create public_dir

        html = '<img src="public/image.png">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert result == html
        assert replaced == set()


class TestPublicFileSecurity:
    """Security-focused tests for `replace_public_files_with_data_uris`.

    These pin the path-traversal and symlink-escape protections expected of
    HTML export — matching the runtime contract documented at
    docs/guides/outputs.md ("Only files within the public directory can be
    accessed; symlinks are not followed; path traversal is blocked").
    """

    def test_dot_dot_traversal(self, tmp_path: Path) -> None:
        """`public/../secret.txt` must not be inlined."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (tmp_path / "secret.txt").write_bytes(b"shh")

        html = '<img src="public/../secret.txt">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert base64.b64encode(b"shh").decode() not in result
        assert replaced == set()

    def test_nested_dot_dot_traversal(self, tmp_path: Path) -> None:
        """Repeated `..` segments must not escape `public/`."""
        public_dir = tmp_path / "public"
        (public_dir / "sub").mkdir(parents=True)
        (tmp_path / "secret.txt").write_bytes(b"shh")

        html = '<img src="public/sub/../../secret.txt">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert base64.b64encode(b"shh").decode() not in result
        assert replaced == set()

    def test_absolute_path_in_subpath(self, tmp_path: Path) -> None:
        """`public//etc/passwd`-style src (pathlib joins abs paths to abs)
        must not read outside `public_dir`."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        outside = tmp_path / "secret.txt"
        outside.write_bytes(b"shh")

        html = f'<img src="public/{outside}">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert base64.b64encode(b"shh").decode() not in result
        assert replaced == set()

    def test_symlink_inside_public_escaping(self, tmp_path: Path) -> None:
        """A symlink inside `public/` pointing at a file outside must be
        rejected (consistent with the runtime `serve_public_file` policy)."""
        import os

        public_dir = tmp_path / "public"
        public_dir.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_bytes(b"shh")

        link = public_dir / "escape.txt"
        try:
            os.symlink(secret, link)
        except (OSError, NotImplementedError):
            import pytest

            pytest.skip("Symlinks not supported on this platform")

        html = '<img src="public/escape.txt">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert base64.b64encode(b"shh").decode() not in result
        assert replaced == set()

    def test_symlink_inside_public_pointing_inside(
        self, tmp_path: Path
    ) -> None:
        """A symlink that stays inside `public/` is allowed (matches the
        runtime policy: containment, not symlink rejection)."""
        import os

        public_dir = tmp_path / "public"
        public_dir.mkdir()
        real = public_dir / "real.png"
        real.write_bytes(b"img")

        link = public_dir / "link.png"
        try:
            os.symlink(real, link)
        except (OSError, NotImplementedError):
            import pytest

            pytest.skip("Symlinks not supported on this platform")

        html = '<img src="public/link.png">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert "data:image/png;base64," in result
        assert base64.b64encode(b"img").decode() in result
        assert replaced == {"public/link.png"}

    def test_directory_reference_not_inlined(self, tmp_path: Path) -> None:
        """A src that resolves to a directory (e.g. `public/.`) must not
        be inlined."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()

        html = '<img src="public/.">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert "data:" not in result
        assert replaced == set()

    def test_oversized_file_is_not_read_into_memory(
        self, tmp_path: Path
    ) -> None:
        """Files exceeding `max_inline_bytes` must be size-checked via
        `stat()` and skipped *without* being read into memory."""
        from unittest.mock import patch

        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (public_dir / "big.bin").write_bytes(b"x" * 1000)

        html = '<img src="public/big.bin">'

        with patch(
            "pathlib.Path.read_bytes",
            side_effect=AssertionError("should not be called"),
        ):
            result, replaced = replace_public_files_with_data_uris(
                html, public_dir=public_dir, max_inline_bytes=100
            )

        assert "data:" not in result
        assert replaced == set()

    def test_symlink_loop_does_not_crash(self, tmp_path: Path) -> None:
        """A symlink loop under `public/` must not crash export.

        On some Python versions `Path.resolve(strict=True)` raises
        `RuntimeError` (not `OSError`) for loops, so the helper has to
        catch it explicitly.
        """
        import os

        public_dir = tmp_path / "public"
        public_dir.mkdir()
        loop_a = public_dir / "a"
        loop_b = public_dir / "b"
        try:
            os.symlink(loop_b, loop_a)
            os.symlink(loop_a, loop_b)
        except (OSError, NotImplementedError):
            import pytest

            pytest.skip("Symlinks not supported on this platform")

        html = '<img src="public/a">'
        # Must not raise.
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert "data:" not in result
        assert replaced == set()

    def test_absolute_public_prefix_not_matched(self, tmp_path: Path) -> None:
        """A bare absolute `/public/...` path (server URL form) must not
        be interpreted as a filesystem-relative public reference."""
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        (public_dir / "image.png").write_bytes(b"img")

        html = '<img src="/public/image.png">'
        result, replaced = replace_public_files_with_data_uris(
            html, public_dir=public_dir
        )

        assert result == html
        assert replaced == set()
