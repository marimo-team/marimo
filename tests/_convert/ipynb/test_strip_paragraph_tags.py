r"""Tests for _strip_paragraph_tags in to_ir.py.

Covers the reviewer suggestions from PR #8674:
- Basic <p>/<\/p> removal
- Preservation of styled <p> tags (with attributes)
- Preservation of content inside fenced code blocks
- Paragraph separation when adjacent </p><p> tags are removed
- Case-insensitive matching
- Inline code protection
"""

from __future__ import annotations

from marimo._convert.ipynb.to_ir import _strip_paragraph_tags


class TestStripParagraphTags:
    def test_basic_removal(self) -> None:
        assert _strip_paragraph_tags("<p>Hello world</p>") == "Hello world"

    def test_preserves_styled_p_tag(self) -> None:
        """Styled <p> tags carry semantic meaning and must be preserved."""
        source = '<p style="color: red">Red text</p>'
        result = _strip_paragraph_tags(source)
        assert '<p style="color: red">' in result
        assert "</p>" in result

    def test_preserves_p_with_class(self) -> None:
        result = _strip_paragraph_tags('<p class="lead">Styled text</p>')
        assert '<p class="lead">' in result
        assert "</p>" in result

    def test_preserves_p_with_id(self) -> None:
        result = _strip_paragraph_tags('<p id="intro">Intro text</p>')
        assert '<p id="intro">' in result

    def test_mixed_bare_and_styled(self) -> None:
        """Bare <p> stripped, styled <p> preserved in same source."""
        source = '<p>Plain text</p>\n<p style="color: blue">Blue text</p>'
        result = _strip_paragraph_tags(source)
        assert "<p>" not in result
        assert "Plain text" in result
        assert '<p style="color: blue">' in result
        assert "Blue text" in result

    def test_case_insensitive(self) -> None:
        assert _strip_paragraph_tags("<P>UPPER</P>") == "UPPER"
        assert _strip_paragraph_tags("<p>Mixed</P>") == "Mixed"

    def test_preserves_other_html_tags(self) -> None:
        source = "<p>Text with <strong>bold</strong> content</p>"
        result = _strip_paragraph_tags(source)
        assert "<strong>bold</strong>" in result
        assert "<p>" not in result

    def test_adjacent_paragraphs_preserve_separation(self) -> None:
        """Closing </p> should become a newline, not vanish."""
        source = "<p>First paragraph</p><p>Second paragraph</p>"
        result = _strip_paragraph_tags(source)
        assert "First paragraph" in result
        assert "Second paragraph" in result
        # The two paragraphs must not be collapsed into one word
        assert "First paragraphSecond" not in result

    def test_fenced_code_block_preserved(self) -> None:
        """<p> tags inside fenced code blocks must not be stripped."""
        source = (
            "<p>Before code</p>\n"
            "```html\n"
            "<p>This is an HTML example</p>\n"
            "```\n"
            "<p>After code</p>"
        )
        result = _strip_paragraph_tags(source)
        # Tags outside code block are removed
        assert result.startswith("Before code")
        assert result.endswith("After code")
        # Tags inside code block are kept
        assert "<p>This is an HTML example</p>" in result

    def test_tilde_fenced_code_block_preserved(self) -> None:
        """Tilde-fenced code blocks are also protected."""
        source = "<p>Intro</p>\n~~~\n<p>Code content</p>\n~~~\n<p>Outro</p>"
        result = _strip_paragraph_tags(source)
        assert "<p>Code content</p>" in result
        assert "<p>Intro" not in result
        assert "<p>Outro" not in result

    def test_multiline_paragraph(self) -> None:
        source = "<p>\nLine 1\nLine 2\n</p>"
        result = _strip_paragraph_tags(source)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "<p>" not in result
        assert "</p>" not in result

    def test_no_tags_passthrough(self) -> None:
        source = "Plain markdown with **bold** and `code`"
        assert _strip_paragraph_tags(source) == source

    def test_empty_string(self) -> None:
        assert _strip_paragraph_tags("") == ""

    def test_latex_not_broken(self) -> None:
        """LaTeX content should pass through unmodified."""
        source = "<p>$E = mc^2$</p>"
        result = _strip_paragraph_tags(source)
        assert "$E = mc^2$" in result
        assert "<p>" not in result

    def test_nested_html_preserved(self) -> None:
        """Non-<p> HTML tags (div, span, etc.) must survive."""
        source = '<p><div class="note">Important</div></p>'
        result = _strip_paragraph_tags(source)
        assert '<div class="note">Important</div>' in result

    def test_adjacent_styled_paragraphs_fully_preserved(self) -> None:
        """Adjacent styled <p> tags must keep both open and close."""
        source = '<p style="color:red">A</p><p style="color:blue">B</p>'
        result = _strip_paragraph_tags(source)
        assert '<p style="color:red">A</p>' in result
        assert '<p style="color:blue">B</p>' in result
