"""Tests for token-aware smart_dedent and fixed_dedent."""

from __future__ import annotations

from marimo._ast.dedent import (
    fixed_dedent,
    smart_dedent,
    split_source_lines,
)


class TestSplitSourceLines:
    def test_default_drops_terminators(self):
        assert split_source_lines("a\nb\n") == ["a", "b", ""]

    def test_normalizes_carriage_returns(self):
        assert split_source_lines("a\r\nb\rc") == ["a", "b", "c"]

    def test_keepends_roundtrips(self):
        for text in ["a\n  b\n", "a\r\nb", "a\rb\n", "x = 1", "", "a\n\nb"]:
            assert "".join(split_source_lines(text, keepends=True)) == text

    def test_keepends_preserves_terminators(self):
        assert split_source_lines("a\r\nb\n", keepends=True) == [
            "a\r\n",
            "b\n",
            "",
        ]

    def test_keepends_element_count_matches_default(self):
        for text in ["a\nb\n", "a\r\nb", "a\rb\n", "x = 1", "", "a\n\nb"]:
            assert len(split_source_lines(text, keepends=True)) == len(
                split_source_lines(text)
            )


class TestSmartDedent:
    def test_basic_dedent(self):
        assert smart_dedent("    x = 1\n    y = 2\n") == "x = 1\ny = 2\n"

    def test_no_indent_noop(self):
        code = "x = 1\ny = 2\n"
        assert smart_dedent(code) == code

    def test_multiline_string_interior_preserved(self):
        code = '    x = """line0\n  two_spaces\n    four_spaces\n      six_spaces"""\n'
        result = smart_dedent(code)
        assert (
            result
            == 'x = """line0\n  two_spaces\n    four_spaces\n      six_spaces"""\n'
        )

    def test_fstring_interior_preserved(self):
        code = '    name = "world"\n    x = f"""hello\n  indented line\n    more indented"""\n'
        result = smart_dedent(code)
        assert "  indented line" in result
        assert "    more indented" in result
        assert result.startswith('name = "world"')

    def test_raw_string_interior_preserved(self):
        code = '    x = r"""line0\n  raw content\n    more raw"""\n'
        result = smart_dedent(code)
        assert "  raw content" in result
        assert "    more raw" in result

    def test_docstring_content_at_column_zero(self):
        code = '    def f():\n        """Cell to compute sum\ne.g. a=1; b=2\nfoo\n"""\n        return a + b\n'
        result = smart_dedent(code)
        assert "e.g. a=1; b=2" in result
        assert result.startswith("def f():")

    def test_single_line_string_not_protected(self):
        code = "    x = 'hello world'\n    y = 2\n"
        assert smart_dedent(code) == "x = 'hello world'\ny = 2\n"

    def test_mixed_code_and_multiline_string_deeper_indent(self):
        # String block indented MORE than surrounding code (block_min >=
        # base_shift) participates in the same dedent, preserving its own
        # internal alignment between SELECT and FROM.
        code = '    def f():\n        sql = """\n            SELECT *\n            FROM t\n        """\n        return sql\n'
        result = smart_dedent(code)
        assert result.startswith("def f():")
        assert "        SELECT *" in result
        assert "        FROM t" in result

    def test_multiline_string_under_indented_relative_to_code(self):
        # String block indented LESS than the surrounding code in places
        # (block_min < base_shift) is left fully untouched, since it can't
        # safely absorb the same dedent without losing structure.
        code = '    def f():\n        text = """\n  shallow\n            deep\n        """\n        return text\n'
        result = smart_dedent(code)
        assert result.startswith("def f():")
        assert "  shallow" in result
        assert "            deep" in result

    def test_top_level_function_with_multiline_docstring(self):
        # Already at zero indent — no-op
        code = '@app.function\ndef foo():\n    """I wonder what\nHappens to this ?\n"""\n    return ...\n'
        result = smart_dedent(code)
        assert result == code

    def test_indented_top_level_function_with_docstring(self):
        code = '    @app.function\n    def foo():\n        """Also wonder what\nHappens to that ?\n"""\n        return ...\n'
        result = smart_dedent(code)
        assert result.startswith("@app.function")
        assert "Happens to that ?" in result


class TestFixedDedent:
    def test_basic(self):
        assert fixed_dedent("    x = 1\n    y = 2") == "x = 1\ny = 2"

    def test_inconsistent_indentation(self):
        result = fixed_dedent("    x = 1\ny = 2")
        assert result == "x = 1\ny = 2"

    def test_multiline_string_preserved(self):
        code = '    x = """line0\n  two_spaces\n    four_spaces"""\n'
        result = fixed_dedent(code)
        assert "  two_spaces" in result
        assert "    four_spaces" in result

    def test_fstring_preserved(self):
        code = '    x = f"""hello\n  indented\n    more"""\n'
        result = fixed_dedent(code)
        assert "  indented" in result
        assert "    more" in result
