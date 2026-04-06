# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import textwrap
from pathlib import Path

from marimo._ast.load import get_notebook_status
from marimo._ast.parse import parse_notebook
from marimo._ast.scanner import scan_notebook, scan_parse_fallback
from marimo._lint.rule_engine import RuleEngine
from marimo._schemas.serialization import UnparsableCell


class TestScanNotebook:
    @staticmethod
    def test_valid_notebook() -> None:
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def one():
                x = 1
                return x,

            @app.cell
            def two():
                y = 2
                return y,

            if __name__ == "__main__":
                app.run()
        """)
        result = scan_notebook(source)
        assert (
            result.preamble.strip()
            == textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()""").strip()
        )
        assert len(result.cells) == 2
        assert result.cells[0].kind == "cell"
        assert result.cells[0].name == "one"
        assert result.cells[0].start_line == 5
        assert result.cells[1].kind == "cell"
        assert result.cells[1].name == "two"
        assert result.cells[1].start_line == 10
        assert result.run_guard_line == 15

    @staticmethod
    def test_various_cell_types() -> None:
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            with app.setup():
                x = 1

            @app.cell
            def one():
                return

            @app.function
            def add(a, b):
                return a + b

            @app.class_definition
            class MyClass:
                pass

            if __name__ == "__main__":
                app.run()
        """)
        result = scan_notebook(source)
        assert len(result.cells) == 4
        assert result.cells[0].kind == "setup"
        assert result.cells[1].kind == "cell"
        assert result.cells[1].name == "one"
        assert result.cells[2].kind == "function"
        assert result.cells[2].name == "add"
        assert result.cells[3].kind == "class_definition"
        assert result.cells[3].name == "MyClass"

    @staticmethod
    def test_decorator_with_args() -> None:
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell(hide_code=True)
            def one():
                x = 1
                return x,

            if __name__ == "__main__":
                app.run()
        """)
        result = scan_notebook(source)
        assert len(result.cells) == 1
        assert result.cells[0].kind == "cell"
        assert result.cells[0].name == "one"

    @staticmethod
    def test_app_cell_inside_string_not_boundary() -> None:
        source = textwrap.dedent('''\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def one():
                x = """
            @app.cell
            def fake():
                pass
            """
                return x,

            @app.cell
            def two():
                return

            if __name__ == "__main__":
                app.run()
        ''')
        result = scan_notebook(source)
        # The @app.cell inside the string should NOT be a boundary
        assert len(result.cells) == 2
        assert result.cells[0].name == "one"
        assert result.cells[1].name == "two"

    @staticmethod
    def test_empty_source() -> None:
        result = scan_notebook("")
        assert result.preamble == ""
        assert result.cells == []
        assert result.run_guard_line is None

    @staticmethod
    def test_header_only() -> None:
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()
        """)
        result = scan_notebook(source)
        assert result.preamble.strip() == source.strip()
        assert result.cells == []
        assert result.run_guard_line is None

    @staticmethod
    def test_no_cell_boundaries() -> None:
        source = "x = 1\ny = 2\nprint(x + y)\n"
        result = scan_notebook(source)
        assert result.preamble == source
        assert result.cells == []
        assert result.run_guard_line is None

    @staticmethod
    def test_unparsable_cell_boundary() -> None:
        source = textwrap.dedent('''\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def one():
                return

            app._unparsable_cell(
                r"""
                _ error
                """,
                name="two"
            )

            if __name__ == "__main__":
                app.run()
        ''')
        result = scan_notebook(source)
        assert len(result.cells) == 2
        assert result.cells[0].kind == "cell"
        assert result.cells[0].name == "one"
        assert result.cells[1].kind == "unparsable"
        assert result.cells[1].name == "two"

    @staticmethod
    def test_unterminated_string_recovery() -> None:
        """Unterminated string in one cell should not prevent
        finding subsequent cell boundaries."""
        source = textwrap.dedent('''\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def broken():
                x = """unterminated
                return

            @app.cell
            def good():
                y = 1
                return y,

            if __name__ == "__main__":
                app.run()
        ''')
        result = scan_notebook(source)
        # Should find at least the second cell via recovery
        assert len(result.cells) >= 1
        # The good cell should be found
        cell_names = [c.name for c in result.cells]
        assert "good" in cell_names


class TestScanParseIntegration:
    """Integration tests using parse_notebook with the scanner pipeline."""

    @staticmethod
    def test_syntax_error_in_one_cell() -> None:
        source = textwrap.dedent('''\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def broken(mo):
                mo.md("""
                r"""Markdown cell with error"""
                """)
                return

            @app.cell
            def _():
                import marimo as mo
                return (mo,)

            @app.cell
            def _():
                return

            if __name__ == "__main__":
                app.run()
        ''')
        notebook = parse_notebook(source)
        assert notebook is not None
        # Should have 3 cells total
        assert len(notebook.cells) == 3
        # First cell should be unparsable
        assert isinstance(notebook.cells[0], UnparsableCell)
        # Other cells should be normal
        assert not isinstance(notebook.cells[1], UnparsableCell)
        assert not isinstance(notebook.cells[2], UnparsableCell)

    @staticmethod
    def test_syntax_errors_in_all_cells() -> None:
        source = textwrap.dedent('''\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def a():
                x = """unterminated
                return

            @app.cell
            def b():
                if if if
                return

            if __name__ == "__main__":
                app.run()
        ''')
        notebook = parse_notebook(source)
        assert notebook is not None
        # All cells should be unparsable
        for cell in notebook.cells:
            assert isinstance(cell, UnparsableCell)

    @staticmethod
    def test_non_marimo_file_syntax_error_does_not_raise() -> None:
        """A file without cell boundaries that has a syntax error should not
        raise — parse_notebook returns a best-effort result so watch/IPC
        are never broken by a syntax error."""
        source = '# Not a marimo file\nprint("hello world\n'
        # Should not raise; returns a non-valid notebook
        result = parse_notebook(source)
        assert result is not None
        assert not result.valid

    @staticmethod
    def test_valid_notebook_unchanged() -> None:
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def one():
                x = 1
                return x,

            @app.cell
            def two(x):
                y = x + 1
                return y,

            if __name__ == "__main__":
                app.run()
        """)
        notebook = parse_notebook(source)
        assert notebook is not None
        assert len(notebook.cells) == 2
        assert notebook.cells[0].code == "x = 1"
        assert notebook.cells[1].code == "y = x + 1"

    @staticmethod
    def test_cell_names_preserved() -> None:
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def alpha():
                x = 1
                return x,

            @app.cell
            def beta(x):
                y = x + 1
                return y,

            if __name__ == "__main__":
                app.run()
        """)
        notebook = parse_notebook(source)
        assert notebook is not None
        assert notebook.cells[0].name == "alpha"
        assert notebook.cells[1].name == "beta"

    @staticmethod
    def test_unparsable_cell_body_extraction() -> None:
        """Unparsable cells should contain only body code,
        not decorator/def/return."""
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def _():
                x = (1 + 2
                y = [3, 4
                return

            @app.cell
            def _():
                return

            if __name__ == "__main__":
                app.run()
        """)
        notebook = parse_notebook(source)
        assert notebook is not None
        assert isinstance(notebook.cells[0], UnparsableCell)
        assert notebook.cells[0].code == "x = (1 + 2\ny = [3, 4"

    @staticmethod
    def test_unparsable_cell_empty_body() -> None:
        """A cell with only a broken return becomes empty."""
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def _():
                if if if
                return

            if __name__ == "__main__":
                app.run()
        """)
        notebook = parse_notebook(source)
        assert notebook is not None
        assert isinstance(notebook.cells[0], UnparsableCell)
        assert notebook.cells[0].code == "if if if"

    @staticmethod
    def test_unparsable_cell_multiline_signature() -> None:
        """Multi-line def signature is properly stripped."""
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def _(
                a,
                b,
            ):
                x = (1 + 2
                return

            if __name__ == "__main__":
                app.run()
        """)
        notebook = parse_notebook(source)
        assert notebook is not None
        assert isinstance(notebook.cells[0], UnparsableCell)
        assert notebook.cells[0].code == "x = (1 + 2"

    @staticmethod
    def test_unparsable_cell_decorator_with_args() -> None:
        """Decorator with arguments is properly stripped."""
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell(hide_code=True)
            def _():
                if if if
                return return return
                return

            if __name__ == "__main__":
                app.run()
        """)
        notebook = parse_notebook(source)
        assert notebook is not None
        assert isinstance(notebook.cells[0], UnparsableCell)
        assert notebook.cells[0].code == "if if if\nreturn return return"

    @staticmethod
    def test_parse_error_in_notebook_file() -> None:
        """Test the actual _test_parse_error_in_notebook.py file."""
        filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "codegen_data/_test_parse_error_in_notebook.py",
        )
        result = get_notebook_status(filepath)
        # Should load with errors, not be broken
        assert result.status == "has_errors"
        assert result.notebook is not None
        assert len(result.notebook.cells) == 3

    @staticmethod
    def test_line_continuation_at_eof_file(tmp_path: object) -> None:
        """Test a notebook with a backslash continuation at EOF.

        The scanner should recover the cell as unparsable and find
        the run guard.
        """
        filepath = Path(str(tmp_path)) / "line_continuation_at_eof.py"
        filepath.write_text(
            textwrap.dedent("""\
                import marimo

                __generated_with = "0.1.0"
                app = marimo.App()


                @app.cell
                def _():
                    x = 1 + \\


                if __name__ == "__main__":
                    app.run()
            """)
        )
        result = get_notebook_status(str(filepath))
        assert result.status == "has_errors"
        assert result.notebook is not None
        assert len(result.notebook.cells) == 1
        assert isinstance(result.notebook.cells[0], UnparsableCell)

    @staticmethod
    def test_scanner_generated_lines_typed() -> None:
        """scan_parse_fallback returns a frozenset of scanner-generated line
        numbers — no untyped AST attribute is used."""
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def good():
                x = 1
                return x,

            @app.cell
            def broken():
                x = (1 + 2
                return

            if __name__ == "__main__":
                app.run()
        """)
        nodes, scanner_lines = scan_parse_fallback(source, "<test>")
        # Only the broken cell's start line should be in scanner_lines
        assert isinstance(scanner_lines, frozenset)
        assert len(scanner_lines) == 1
        # The good cell was parsed successfully — not scanner-generated
        good_lines = {n.lineno for n in nodes if hasattr(n, "lineno")}
        broken_line = next(iter(scanner_lines))
        assert broken_line in good_lines  # the line exists in the node list
        assert len(nodes) > 0

    @staticmethod
    def test_scanner_generated_lines_existing_unparsable_not_flagged() -> None:
        """Pre-existing app._unparsable_cell() in source must NOT appear in
        scanner_generated_lines — only cells the scanner itself created."""
        # This source parses fine (ast.parse succeeds), so scan_parse_fallback
        # returns ([], frozenset()) — no scanner-generated lines.
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            app._unparsable_cell(
                r\"\"\"_ error\"\"\",
                name="broken"
            )

            if __name__ == "__main__":
                app.run()
        """)
        nodes, scanner_lines = scan_parse_fallback(source, "<test>")
        # The pre-existing unparsable cell parsed fine through the scanner
        # (its source is valid Python), so scanner_lines must be empty.
        assert len(nodes) > 0
        assert scanner_lines == frozenset()

    @staticmethod
    def test_line_continuation_no_duplicate_diagnostics() -> None:
        """Scanner-generated unparsable cells should produce only
        one diagnostic (MB001), not a duplicate from MF001."""
        source = textwrap.dedent("""\
            import marimo
            __generated_with = "0.1.0"
            app = marimo.App()

            @app.cell
            def _():
                x = 1 + \\

            if __name__ == "__main__":
                app.run()
        """)
        notebook = parse_notebook(source)
        assert notebook is not None
        assert len(notebook.cells) == 1
        assert isinstance(notebook.cells[0], UnparsableCell)

        # Run linter rules
        engine = RuleEngine.create_default()
        diagnostics = engine.check_notebook_sync(notebook)

        # Should have exactly one diagnostic for the unparsable cell (MB001),
        # NOT a duplicate from MF001 (general-formatting)
        unparsable_diags = [d for d in diagnostics if d.code == "MB001"]
        scanner_format_diags = [
            d
            for d in diagnostics
            if d.code == "MF001" and "syntax error" in d.message.lower()
        ]
        assert len(unparsable_diags) == 1
        assert len(scanner_format_diags) == 0

    @staticmethod
    def test_encoding_error_file(tmp_path: object) -> None:
        """Test a notebook with non-UTF-8 bytes (encoding error).

        The file declares ASCII encoding but has a Latin-1 byte (0xe9).
        Should load gracefully with errors, not crash.
        """
        tmp = Path(str(tmp_path))
        filepath = tmp / "encoding_errors.py"
        # Write raw bytes: ASCII encoding declaration + Latin-1 byte 0xe9
        filepath.write_bytes(
            b"# -*- coding: ascii -*-\n"
            b"import marimo\n"
            b"\n"
            b'__generated_with = "0.0.0"\n'
            b"app = marimo.App()\n"
            b"\n"
            b"\n"
            b"@app.cell\n"
            b"def _():\n"
            b'    x = "caf\xe9"\n'
            b"    return\n"
            b"\n"
            b"\n"
            b'if __name__ == "__main__":\n'
            b"    app.run()\n"
        )
        result = get_notebook_status(str(filepath))
        # Should load (not crash), with errors from the encoding issue
        assert result.status in ("has_errors", "valid")
        assert result.notebook is not None
        assert len(result.notebook.cells) >= 1
