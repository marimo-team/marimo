# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os

from marimo._ast.parse import Parser, parse_notebook

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_filepath(name: str) -> str:
    return os.path.join(DIR_PATH, f"codegen_data/{name}.py")


# NB. Some barebones testing at the areas that seemed to be most sensitive.
# Note that loader should cover these cases and more by proxy.
class TestParser:
    @staticmethod
    def test_parse_codes() -> None:
        parser = Parser(get_filepath("test_generate_filecontents"))
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
        parser = Parser(get_filepath("test_get_setup_blank"))
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
            get_filepath("test_generate_filecontents_toplevel")
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
        parser = Parser(get_filepath("test_app_with_only_comments"))
        body = parser.node_stack()
        header_result = parser.parse_header(body)
        assert header_result

        import_result = parser.parse_import(body)
        assert not import_result

    @staticmethod
    def test_just_app() -> None:
        notebook = parse_notebook(get_filepath("test_get_app_kwargs"))
        # No generated with, or run guard
        assert len(notebook.violations) == 2
        assert "generated_with" in notebook.violations[0].description
        assert "run guard" in notebook.violations[1].description

    @staticmethod
    def test_parse_messy_toplevel() -> None:
        notebook = parse_notebook(
            get_filepath("test_get_codes_messy_toplevel")
        )
        assert notebook
        # unexpected statements and a missing run guard
        assert len(notebook.violations) == 3
        assert "statement" in notebook.violations[0].description
        assert "statement" in notebook.violations[1].description
        assert "run guard" in notebook.violations[2].description
