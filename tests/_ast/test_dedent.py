"""Tests for token-aware smart_dedent and fixed_dedent."""

from __future__ import annotations

from marimo._ast.dedent import fixed_dedent, smart_dedent


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

    def test_mixed_code_and_multiline_string(self):
        code = '    def f():\n        sql = """\n            SELECT *\n            FROM t\n        """\n        return sql\n'
        result = smart_dedent(code)
        assert result.startswith("def f():")
        assert "            SELECT *" in result
        assert "            FROM t" in result

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
