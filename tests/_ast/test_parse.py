# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import ast
from pathlib import Path

from marimo._ast.parse import Parser, _eval_kwargs, parse_notebook

DIR_PATH = Path(__file__).parent


def get_filepath(name: str) -> Path:
    return DIR_PATH / f"codegen_data/{name}.py"


# NB. Some barebones testing at the areas that seemed to be most sensitive.
# Note that loader should cover these cases and more by proxy.
class TestParser:
    @staticmethod
    def test_main() -> None:
        notebook = parse_notebook(get_filepath("test_main").read_text())
        # Should just work without any violations.
        assert len(notebook.violations) == 0

    @staticmethod
    def test_parse_codes() -> None:
        parser = Parser.from_file(get_filepath("test_generate_filecontents"))
        body = parser.node_stack()
        body_result = parser.parse_body(body)
        assert body_result
        cells = body_result.unwrap()
        assert len(cells) == 5
        assert [cell.name for cell in cells] == [
            "one",
            "two",
            "three",
            "four",
            "five",
        ]

    @staticmethod
    def test_parse_setup_blank() -> None:
        parser = Parser.from_file(get_filepath("test_get_setup_blank"))
        body = parser.node_stack()
        _ = parser.parse_header(body)
        setup_result = parser.parse_setup(body)
        assert setup_result, setup_result.violations
        setup_cell = setup_result.unwrap()
        assert setup_cell.name == "setup"
        assert setup_cell.code == "# Only comments\n# and a pass"

    @staticmethod
    def test_parse_codes_toplevel() -> None:
        notebook = parse_notebook(
            get_filepath("test_generate_filecontents_toplevel").read_text()
        )
        assert notebook
        assert notebook.header.value.startswith(
            "# This comment should be preserved"
        )
        # Likely over extended scope in this case.
        assert "import marimo" not in notebook.header.value

        assert [cell.name for cell in notebook.cells] == [
            "setup",
            "_",
            "addition",
            "shadow_case",
            "_",
            "_",
            "fun_that_uses_mo",
            "fun_that_uses_another_but_out_of_order",
            "fun_uses_file",
            "fun_that_uses_another",
            "cell_with_ref_and_def",
            "_",
            "ExampleClass",
            "SubClass",
        ]

    @staticmethod
    def test_parse_app_with_only_comments() -> None:
        parser = Parser.from_file(get_filepath("test_app_with_only_comments"))
        body = parser.node_stack()
        header_result = parser.parse_header(body)
        assert header_result

        import_result = parser.parse_import(body)
        assert not import_result

    @staticmethod
    def test_just_app() -> None:
        notebook = parse_notebook(
            get_filepath("test_get_app_kwargs").read_text()
        )
        # No generated with, or run guard
        assert len(notebook.violations) == 2
        assert "generated_with" in notebook.violations[0].description
        assert "run guard" in notebook.violations[1].description

    @staticmethod
    def test_parse_messy_toplevel() -> None:
        notebook = parse_notebook(
            get_filepath("test_get_codes_messy_toplevel").read_text()
        )
        assert notebook
        # unexpected statements and a missing run guard
        assert len(notebook.violations) == 3
        assert "generated" in notebook.violations[0].description
        assert "statement" in notebook.violations[1].description
        assert "run guard" in notebook.violations[2].description

    @staticmethod
    def test_parse_syntax_errors() -> None:
        notebook = parse_notebook(
            get_filepath("test_syntax_errors").read_text()
        )
        assert notebook
        # Valid currently
        # TODO: Propagate decorators violations.
        assert len(notebook.violations) == 0
        assert [cell.name for cell in notebook.cells] == [
            "global_error",
            "return_error",
        ]

    @staticmethod
    def test_parse_decorator_permutations() -> None:
        notebook = parse_notebook(get_filepath("test_decorators").read_text())
        assert notebook
        # Valid currently
        # TODO: Propagate decorators violations.
        assert len(notebook.violations) == 0

    @staticmethod
    def test_eval_kwargs_with_list_constants() -> None:
        """Test that _eval_kwargs correctly handles list constants in kwargs."""
        # Test case: marimo.App(width="medium", auto_download=["html"])

        # Create AST nodes for the keyword arguments
        width_kw = ast.keyword(arg="width", value=ast.Constant(value="medium"))

        auto_download_kw = ast.keyword(
            arg="auto_download",
            value=ast.List(elts=[ast.Constant(value="html")], ctx=ast.Load()),
        )

        keywords = [width_kw, auto_download_kw]

        # Test the function
        kwargs, violations = _eval_kwargs(keywords)

        # Verify results
        assert len(violations) == 0
        assert kwargs["width"] == "medium"
        assert kwargs["auto_download"] == ["html"]

    @staticmethod
    def test_eval_kwargs_with_invalid_list_elements() -> None:
        """Test that _eval_kwargs handles invalid elements in list kwargs."""
        # Create a list with both valid and invalid elements
        invalid_name_node = ast.Name(id="invalid_var", ctx=ast.Load())
        invalid_name_node.lineno = 1
        invalid_name_node.col_offset = 0

        invalid_list_kw = ast.keyword(
            arg="test_arg",
            value=ast.List(
                elts=[
                    ast.Constant(value="valid"),
                    invalid_name_node,  # Invalid: not a constant
                ],
                ctx=ast.Load(),
            ),
        )

        keywords = [invalid_list_kw]

        # Test the function
        kwargs, violations = _eval_kwargs(keywords)

        # Should have one violation for the invalid element
        assert len(violations) == 1
        assert kwargs["test_arg"] == [
            "valid"
        ]  # Should still include valid elements

    @staticmethod
    def test_parse_non_marimo() -> None:
        import pytest

        from marimo._ast.parse import MarimoFileError

        # Non-marimo files that have marimo imports but no App definition
        # should raise MarimoFileError with the expected message
        with pytest.raises(
            MarimoFileError, match="`marimo.App` definition expected."
        ):
            parse_notebook(get_filepath("test_non_marimo").read_text())
