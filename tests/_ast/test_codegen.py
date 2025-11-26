# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import json
from functools import partial
from inspect import cleandoc
from pathlib import Path
from textwrap import dedent
from typing import Any, Optional
from unittest.mock import patch

import codegen_data.test_main as mod
import pytest

from marimo import __version__
from marimo._ast import codegen, compiler, load
from marimo._ast.app import App, InternalApp
from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._ast.names import is_internal_cell_name
from marimo._schemas.notebook import NotebookV1

compile_cell = partial(compiler.compile_cell, cell_id="0")

DIR_PATH = Path(__file__).parent


def get_expected_filecontents(name: str) -> str:
    contents = get_filepath(name).read_text()
    lines = contents.split("\n")
    break_index = None
    for i, line in enumerate(lines):
        if line.startswith("__generated_with"):
            break_index = i
            break
    assert break_index is not None
    return "\n".join(
        lines[:break_index]
        + [f'__generated_with = "{__version__}"']
        + lines[break_index + 1 :]
    )


def get_filepath(name: str) -> Path:
    return Path(DIR_PATH) / f"codegen_data/{name}.py"


def sanitized_version(output: str) -> str:
    return output.replace(__version__, "0.0.0")


def wrap_generate_filecontents(
    codes: list[str],
    names: list[str],
    cell_configs: Optional[list[CellConfig]] = None,
    **kwargs: Any,
) -> str:
    """
    Wraps codegen.generate_filecontents to make the
    cell_configs argument optional."""
    if cell_configs is None:
        resolved_configs = [CellConfig() for _ in range(len(codes))]
    else:
        resolved_configs = cell_configs
    filecontents = codegen.generate_filecontents(
        codes, names, cell_configs=resolved_configs, **kwargs
    )
    # leading spaces should be removed too
    assert filecontents.lstrip() == filecontents
    return filecontents


async def get_idempotent_marimo_source(name: str) -> str:
    from marimo._utils.formatter import Formatter

    path = get_filepath(name)
    app = load.load_app(str(path))
    header_comments = codegen.get_header_comments(path)
    generated_contents = codegen.generate_filecontents(
        codes=list(app._cell_manager.codes()),
        names=list(app._cell_manager.names()),
        cell_configs=list(app._cell_manager.configs()),
        config=app._config,
        header_comments=header_comments,
    )
    generated_contents = sanitized_version(generated_contents)

    python_source = sanitized_version(path.read_text())

    formatted = await Formatter(codegen.MAX_LINE_LENGTH).format(
        {"source": python_source, "generated": generated_contents}
    )

    assert formatted["source"] == formatted["generated"]
    return formatted["generated"]


class TestGeneration:
    @staticmethod
    def test_generate_filecontents_empty() -> None:
        contents = wrap_generate_filecontents([], [])
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_empty"
        )

    @staticmethod
    def test_generate_filecontents_empty_with_config() -> None:
        config = _AppConfig(
            app_title="test_title", width="full", css_file=r"a\b.css"
        )
        contents = wrap_generate_filecontents([], [], config=config)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_empty_with_config"
        )

    @staticmethod
    def test_generate_filecontents() -> None:
        cell_one = "import numpy as np"
        cell_two = "x = 0\nxx = 1"
        cell_three = "y = x + 1"
        cell_four = "# comment\nz = np.array(x + y)"
        cell_five = "# just a comment"
        codes = [cell_one, cell_two, cell_three, cell_four, cell_five]
        names = ["one", "two", "three", "four", "five"]
        contents = wrap_generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents"
        )

    @staticmethod
    def test_generate_filecontents_async() -> None:
        cell_one = "import numpy as np\nimport asyncio"
        cell_two = "x = 0\nxx = 1\nawait asyncio.sleep(1)"
        cell_three = "async def _():\n    await asyncio.sleep(x)"
        codes = [cell_one, cell_two, cell_three]
        names = ["one", "two", "three"]
        contents = wrap_generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_async"
        )

    @staticmethod
    def test_generate_filecontents_async_long_signature() -> None:
        cell_one = cleandoc(
            """
            (
                client,
                get_calculation_trigger,
                get_components_configuration,
                get_conditions_state,
            ) = (1, 1, 1, 1)
            """
        )
        cell_two = cleandoc(
            """
            _conditions = [c for c in get_conditions_state().values()]
            _configuration = get_components_configuration()

            _configuration_conditions_list = {
                "configuration": _configuration,
                "condition": _conditions,
            }

            _trigger = get_calculation_trigger()

            async for data_point in client("test", "ws://localhost:8000"):
                print(data_point)
            data_point
            """
        )
        codes = [cell_one, cell_two]
        names = ["one", "two"]
        contents = wrap_generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_async_long_signature"
        )

    @staticmethod
    def test_generate_filecontents_single_cell() -> None:
        cell_one = "import numpy as np"
        codes = [cell_one]
        names = ["one"]
        contents = wrap_generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_single_cell"
        )

    @staticmethod
    def test_generate_filecontents_with_syntax_error() -> None:
        cell_one = "import numpy as np"
        cell_two = "_ error"
        cell_three = "'all good'"
        cell_four = '_ another_error\n_ and """another"""\n\n    \\t'
        codes = [cell_one, cell_two, cell_three, cell_four]
        names = ["one", "two", "__", "__"]
        contents = wrap_generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_with_syntax_error"
        )

    @staticmethod
    def test_generate_unparsable_cell() -> None:
        code = "    error\n\\t"
        raw = codegen.generate_unparsable_cell(code, None, CellConfig())
        stringified = eval("\n".join(raw.split("\n")[1:5])).split("\n")
        # first line empty
        assert not stringified[0]
        # leading 4 spaces followed by source line
        assert stringified[1] == " " * 4 + "    error"
        # leading 4 spaces followed by source line
        assert stringified[2] == " " * 4 + "\\t"
        # leading 4 spaces followed by nothing
        assert stringified[3] == " " * 4

    @staticmethod
    def test_generate_unparsable_cell_with_await() -> None:
        code = "    await error\n\\t"
        raw = codegen.generate_unparsable_cell(code, None, CellConfig())
        stringified = eval("\n".join(raw.split("\n")[1:5])).split("\n")
        # first line empty
        assert not stringified[0]
        # leading 4 spaces followed by source line
        assert stringified[1] == " " * 4 + "    await error"
        # leading 4 spaces followed by source line
        assert stringified[2] == " " * 4 + "\\t"
        # leading 4 spaces followed by nothing
        assert stringified[3] == " " * 4

    @staticmethod
    def test_generate_unparsable_cell_with_config() -> None:
        """Test that generate_unparsable_cell works with non-default CellConfig."""
        code = 'mo.md("markdown in marimo")'
        config = CellConfig(hide_code=True)

        # This should not raise AttributeError
        raw = codegen.generate_unparsable_cell(code, None, config)

        # Verify the config is included in the output
        assert "hide_code=True" in raw
        # Verify the code is properly escaped and included
        assert 'mo.md(\\"markdown in marimo\\")' in raw

    @staticmethod
    def test_long_line_in_main() -> None:
        cell_one = "\n".join(
            [
                "i_am_a_very_long_name = 0",
                "i_am_another_very_long_name = 0",
                "yet_another_very_long_name = 0",
            ]
        )
        cell_two = (
            "z = i_am_a_very_long_name + "
            + "i_am_another_very_long_name + "
            + "yet_another_very_long_name"
        )
        contents = wrap_generate_filecontents(
            [cell_one, cell_two], ["one", "two"]
        )
        assert contents == get_expected_filecontents("test_long_line_in_main")

    @staticmethod
    def test_generate_filecontents_unshadowed_builtin() -> None:
        cell_one = "type"
        codes = [cell_one]
        names = ["one"]
        contents = wrap_generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_unshadowed_builtin"
        )

    @staticmethod
    def test_generate_filecontents_shadowed_builtin() -> None:
        cell_one = "type = 1"
        cell_two = "type"
        codes = [cell_one, cell_two]
        names = ["one", "two"]
        contents = wrap_generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_shadowed_builtin"
        )

    @staticmethod
    def test_generate_filecontents_duplicate_definitions() -> None:
        """Test that duplicate top-level definitions don't cause KeyError during codegen."""
        cell_one = "def Two(): return 2"
        cell_two = "def Two(): return 'two'"
        codes = [cell_one, cell_two]
        names = ["one", "two"]
        # This should not raise a KeyError during TopLevelExtraction
        # (duplicate validation happens at app.run(), not during codegen)
        contents = wrap_generate_filecontents(codes, names)
        # Should successfully generate file contents
        assert "import marimo" in contents
        assert contents is not None

    def test_with_second_type_noop(self) -> None:
        referring = "x = 1; x: int = 0"
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x + 0"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo", variable_data=ref_vars)
        expected = "\n".join(
            [
                "@app.cell",
                "def foo(x):",
                "    z = x + 0",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_with_types(self) -> None:
        referring = "x: int = 0"
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x + 0"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo", variable_data=ref_vars)
        expected = "\n".join(
            [
                "@app.cell",
                "def foo(x: int):",
                "    z = x + 0",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_with_toplevel_types(self) -> None:
        referring = "x: T = 1"
        ref_vars = compile_cell(referring).init_variable_data

        code = "z: T = x + 0"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(
            cell, "foo", allowed_refs={"T"}, variable_data=ref_vars
        )
        expected = "\n".join(
            [
                "@app.cell",
                "def foo(x: T):",
                "    z: T = x + 0",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_with_string_types(self) -> None:
        referring = 'x: "int" = 0'
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x + 0"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo", variable_data=ref_vars)
        expected = "\n".join(
            [
                "@app.cell",
                'def foo(x: "int"):',
                "    z = x + 0",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_with_nested_string_types(self) -> None:
        referring = '''x: "TT[\\"i\\"]" = 0; A:"""
        a new line type"""'''
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x + 0"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo", variable_data=ref_vars)
        expected = "\n".join(
            [
                "@app.cell",
                "def foo(x: 'TT[\"i\"]'):",
                "    z = x + 0",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_with_unknown_types(self) -> None:
        referring = "x: something = 0"
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x + 0"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo", variable_data=ref_vars)
        expected = "\n".join(
            [
                "@app.cell",
                'def foo(x: "something"):',
                "    z = x + 0",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_literal_quote_standardization(self) -> None:
        """Test that Literal type annotations are standardized to double quotes.

        Regression test for https://github.com/marimo-team/marimo/issues/6446
        """
        # Test that single quotes in Literal are standardized to double quotes
        referring = "x: Literal['foo', 'bar'] = 'foo'"
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(
            cell, "foo", allowed_refs={"Literal"}, variable_data=ref_vars
        )
        expected = "\n".join(
            [
                "@app.cell",
                'def foo(x: Literal["foo", "bar"]):',
                "    z = x",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_quote_standardization_edge_cases(self) -> None:
        """Test edge cases for quote standardization in type annotations."""
        # Test mixed quotes where double quotes are preserved
        referring = 'x: Literal["foo", \'bar\'] = "foo"'
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(
            cell, "foo", allowed_refs={"Literal"}, variable_data=ref_vars
        )
        expected = "\n".join(
            [
                "@app.cell",
                'def foo(x: Literal["foo", "bar"]):',
                "    z = x",
                "    return (z,)",
            ]
        )
        assert fndef == expected

        # Test nested quotes that should remain single due to containing double quotes
        referring = "x: Literal['say \"hello\"'] = 'say \"hello\"'"
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(
            cell, "foo", allowed_refs={"Literal"}, variable_data=ref_vars
        )
        expected = "\n".join(
            [
                "@app.cell",
                "def foo(x: Literal['say \"hello\"']):",
                "    z = x",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_quote_nested_edge_cases(self) -> None:
        """Test edge cases for quote standardization in type annotations."""
        # Test mixed quotes where double quotes are preserved
        referring = 'x: tuple[tuple[Literal["foo", \'bar\']]] = "((foo,),)"'
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(
            cell, "foo", allowed_refs={"tuple"}, variable_data=ref_vars
        )
        expected = "\n".join(
            [
                "@app.cell",
                'def foo(x: "tuple[tuple[Literal[\\"foo\\", \\"bar\\"]]]"):',
                "    z = x",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_quote_nested_esscaped_edge_cases(self) -> None:
        referring = "x: Literal['say \"hello\"'] = 'say \"hello\"'"
        ref_vars = compile_cell(referring).init_variable_data

        code = "z = x"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(
            cell, "foo", allowed_refs=set(), variable_data=ref_vars
        )
        expected = "\n".join(
            [
                "@app.cell",
                'def foo(x: "Literal[\'say \\"hello\\"\']"):',
                "    z = x",
                "    return (z,)",
            ]
        )
        assert fndef == expected

    def test_safe_serialize_cell_handles_syntax_error(self) -> None:
        """Test that safe_serialize_cell falls back when ast_parse fails.

        This test mocks ast_parse to fail, exercising the except block in
        safe_serialize_cell that falls back to generate_unparsable_cell.
        Goes through the full codegen path via generate_filecontents.
        """
        # Create a simple cell that would normally serialize fine
        code = "x = 1"
        name = "test_cell"

        # Mock ast_parse to raise SyntaxError and mock the logger
        with (
            patch("marimo._ast.codegen.ast_parse") as mock_ast_parse,
            patch("marimo._ast.codegen.LOGGER.warning") as mock_warning,
        ):
            mock_ast_parse.side_effect = SyntaxError("Mock syntax error")

            # Go through the full codegen path
            result = wrap_generate_filecontents([code], [name])

            # Verify ast_parse was called
            assert mock_ast_parse.called

            # Verify the result contains an unparsable cell format
            # (it should contain the original code)
            assert "x = 1" in result
            # Unparsable cells use app._unparsable_cell wrapper
            assert "app._unparsable_cell" in result
            # Verify it has the cell name
            assert name in result

            # Verify warning was logged with the correct message
            assert mock_warning.called
            warning_message = mock_warning.call_args[0][0]
            assert "falling back to unparsable cell" in warning_message
            assert name in warning_message
            assert "Mock syntax error" in warning_message

    @staticmethod
    def test_generate_app_constructor_with_auto_download() -> None:
        config = _AppConfig(
            width="full",
            app_title="Test App",
            css_file="custom.css",
            auto_download=["html", "markdown"],
        )
        result = codegen.generate_app_constructor(config)
        expected = (
            "app = marimo.App(\n"
            '    width="full",\n'
            '    app_title="Test App",\n'
            '    css_file="custom.css",\n'
            '    auto_download=["html", "markdown"],\n'
            ")"
        )
        assert result == expected

    @staticmethod
    def test_generate_app_constructor_with_empty_auto_download() -> None:
        config = _AppConfig(auto_download=[])
        result = codegen.generate_app_constructor(config)
        assert result == "app = marimo.App()"

    @staticmethod
    def test_generate_app_constructor_with_single_auto_download() -> None:
        config = _AppConfig(auto_download=["html"])
        result = codegen.generate_app_constructor(config)
        assert result == 'app = marimo.App(auto_download=["html"])'

    @staticmethod
    def test_generate_file_contents_overwrite_default_cell_names() -> None:
        contents = wrap_generate_filecontents(
            ["import numpy as np", "x = 0", "y = x + 1"],
            ["is_named", "__", "__"],
        )
        # __9 and __10 are overwritten by the default names
        assert "is_named" in contents
        assert "def _" in contents
        assert "def __" not in contents

    @staticmethod
    async def test_generate_filecontents_toplevel() -> None:
        source = await get_idempotent_marimo_source(
            "test_generate_filecontents_toplevel"
        )
        assert "import marimo" in source
        split = source.split("import marimo")
        # The default one, the as mo in top level, in as mo in cell
        assert len(split) == 3

    @staticmethod
    async def test_generate_filecontents_toplevel_pytest() -> None:
        source = await get_idempotent_marimo_source(
            "test_generate_filecontents_toplevel_pytest"
        )
        assert "import marimo" in source

    @staticmethod
    async def test_generate_filecontents_with_annotation_typing() -> None:
        source = await get_idempotent_marimo_source(
            "test_app_with_annotation_typing"
        )
        assert "import marimo" in source


@pytest.fixture
def marimo_app() -> App:
    return mod.app


class TestApp:
    @staticmethod
    def test_run(marimo_app: App) -> None:
        outputs, defs = marimo_app.run()
        assert outputs == (None, "z", None)
        assert defs == {"x": 0, "y": 1, "z": 2, "a": 1}

    @staticmethod
    def test_app_with_title(marimo_app: App) -> None:
        """Update title in app config"""
        NEW_TITLE = "test_title"
        marimo_internal_app = InternalApp(marimo_app)
        assert marimo_internal_app.config.app_title is None
        marimo_internal_app.update_config({"app_title": NEW_TITLE})
        assert marimo_internal_app.config.app_title == "test_title"


class TestToFunctionDef:
    def test_tofunctiondef_one_def(self) -> None:
        code = "x = 0"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo():", "    x = 0", "    return (x,)"]
        )
        assert fndef == expected

    def test_tofunctiondef_one_ref(self) -> None:
        code = "y + 1"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo(y):", "    y + 1", "    return"]
        )
        assert fndef == expected

    def test_tofunctiondef_empty_cells(self) -> None:
        code = ""
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(["@app.cell", "def foo():", "    return"])

        code = "\n #\n"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = cleandoc(
            """
            @app.cell
            def foo():

                 #

                return
            """
        )
        assert fndef == expected

    def test_tofunctiondef_builtin_not_a_ref(self) -> None:
        code = "print(y)"
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo(y):", "    print(y)", "    return"]
        )
        assert fndef == expected

    def test_tofunctiondef_refs_and_defs(self) -> None:
        code = "\n".join(["y = x", "z = x", "z = w + y"])
        cell = compile_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo(w, x):"]
            + ["    " + line for line in code.split("\n")]
            + ["    return y, z"]
        )
        assert fndef == expected

    def test_with_empty_config(self) -> None:
        code = "x = 0"
        cell = compile_cell(code)
        cell = cell.configure(CellConfig())
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo():", "    x = 0", "    return (x,)"]
        )
        assert fndef == expected

    def test_with_some_config(self) -> None:
        code = "x = 0"
        cell = compile_cell(code)
        cell = cell.configure(CellConfig(disabled=True))
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            [
                "@app.cell(disabled=True)",
                "def foo():",
                "    x = 0",
                "    return (x,)",
            ]
        )
        assert fndef == expected

    def test_with_all_config(self) -> None:
        code = "x = 0"
        cell = compile_cell(code)
        cell = cell.configure(CellConfig(disabled=True, hide_code=True))
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            [
                "@app.cell(disabled=True, hide_code=True)",
                "def foo():",
                "    x = 0",
                "    return (x,)",
            ]
        )
        assert fndef == expected

    def test_dotted_names_filtered_from_signature(self) -> None:
        """Test that dotted names (like SQL schema.table references) are filtered out from function signatures."""
        # Create a cell with a dotted reference in refs (simulating SQL schema.table)
        code = "result = some_function()"
        cell = compile_cell(code)

        # Manually add a dotted reference to simulate SQL schema.table reference
        # This would normally happen when SQL references are parsed
        cell.refs.add("my_schema.pokemon_db")

        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            [
                "@app.cell",
                "def foo(some_function):",
                "    result = some_function()",
                "    return (result,)",
            ]
        )
        assert fndef == expected

        # Verify that the dotted name is not in the function signature
        assert "my_schema.pokemon_db" not in fndef
        assert "def foo(my_schema.pokemon_db" not in fndef

    def test_sql_defs_filtered_from_return(self) -> None:
        """Test that SQL definitions are filtered from return but can still be referenced."""

        # Cell 1: defines a SQL variable (cars) - should NOT be in return
        code1 = "empty = mo.sql('CREATE TABLE cars_df ();')"
        # Cell 2: uses the SQL variable (cars) - should appear in signature
        code2 = "result = cars_df.filter(lambda x: x > 0); empty"
        expected = wrap_generate_filecontents(
            [code1, code2], ["cell1", "cell2"]
        )
        assert (
            "\n".join(
                [
                    "@app.cell",
                    "def cell1(mo):",
                    "    empty = mo.sql('CREATE TABLE cars_df ();')",
                    "    return (empty,)",  # Doesn't return cars_df
                    "",
                    "",
                    "@app.cell",
                    "def cell2(cars_df, empty):",
                    "    result = cars_df.filter(lambda x: x > 0); empty",
                    "    return",
                ]
            )
            in expected
        )

    def test_should_remove_defaults(self) -> None:
        code = "x = 0"
        cell = compile_cell(code)
        cell = cell.configure(CellConfig(disabled=False, hide_code=False))
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            [
                "@app.cell",
                "def foo():",
                "    x = 0",
                "    return (x,)",
            ]
        )
        assert fndef == expected

    def test_fn_with_empty_config(self) -> None:
        code = "\n".join(["def foo():", "    x = 0", "    return (x,)"])
        cell = compile_cell(code)
        cell = cell.configure(CellConfig())
        fndef = codegen.to_top_functiondef(cell)
        expected = "@app.function\n" + code
        assert fndef == expected

    def test_fn_with_all_config(self) -> None:
        code = "\n".join(["def foo():", "    x = 0", "    return (x,)"])
        cell = compile_cell(code)
        cell = cell.configure(CellConfig(disabled=True, hide_code=True))
        fndef = codegen.to_top_functiondef(cell)
        expected = "@app.function(disabled=True, hide_code=True)\n" + code
        assert fndef == expected


def test_markdown_invalid() -> None:
    expected = wrap_generate_filecontents(
        ['mo.md("Unclosed string)', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise
    expected = wrap_generate_filecontents(
        ['mo.md("Unclosed call"', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Unparsable: triple quotes close prematurely leaving invalid syntax
    expected = wrap_generate_filecontents(
        ['mo.md("""some text """ and more)', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Unparsable: triple quotes in middle breaking the call
    expected = wrap_generate_filecontents(
        ['mo.md("""content """ extra stuff""")', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Unparsable: f-string with triple quotes breaking syntax
    expected = wrap_generate_filecontents(
        ['mo.md(f"""value {x} """ broken)', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Unparsable: nested quotes causing premature closure
    expected = wrap_generate_filecontents(
        ['mo.md("""text with """ in middle""")', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Unparsable: double-quoted string with triple quotes breaking it
    expected = wrap_generate_filecontents(
        ['mo.md("some """ text")', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Unparsable: f-string with triple quotes inside interpolation
    expected = wrap_generate_filecontents(
        ['mo.md(f"value {"""test"""} more")', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Unparsable: f-string with triple quotes breaking the f-string itself
    expected = wrap_generate_filecontents(
        ['mo.md(f"text """ {x}")', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Unparsable: triple-quoted f-string with triple quotes in content
    expected = wrap_generate_filecontents(
        ['mo.md(f"""start """ middle {y}""")', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Unparsable: f-string with triple quotes AND invalid syntax in interpolation
    expected = wrap_generate_filecontents(
        ['mo.md(f"text {$$$}")', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Unparsable: unclosed triple-quote docstring with content
    expected = wrap_generate_filecontents(
        ['"""unclosed docstring\nwith """ content', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Unparsable: broken f-string with triple quotes
    expected = wrap_generate_filecontents(
        ['f"value {x} with """', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Unparsable: string with triple quotes not closed properly
    expected = wrap_generate_filecontents(
        ['"string content """', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # 0.17.3 parse variation
    expected = wrap_generate_filecontents(
        [
            '''mo.md("
            r"""some text"""
        )''',
            "import marimo as mo",
        ],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise


def test_markdown_with_alt_strings() -> None:
    # Basic triple quotes in middle
    expected = wrap_generate_filecontents(
        ['mo.md(\'has """\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    expected = wrap_generate_filecontents(
        ['mo.md(\'has """\\"\\\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Triple quotes at start
    expected = wrap_generate_filecontents(
        ['mo.md(\'"""followed by text\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Triple quotes at end
    expected = wrap_generate_filecontents(
        ['mo.md(\'text followed by"""\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Only triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'"""\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Multiple triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'first""" middle """end\')', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Four consecutive quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'Text with """"more\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Five consecutive quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'Text with """""more\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Six consecutive quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'Text with """"""more\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Escaped quote before triple
    expected = wrap_generate_filecontents(
        ['mo.md(\'Text with \\\\"""""more\')', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Triple quotes with whitespace
    expected = wrap_generate_filecontents(
        ['mo.md(\' """ \')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Inline code with triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'Use `"""` for docstrings\')', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # HTML/markdown with triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'<div>"""</div>\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # JSON with many quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'{"key": """value"""}\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # With headers
    expected = wrap_generate_filecontents(
        ['mo.md(\'# Header with """\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # With links
    expected = wrap_generate_filecontents(
        ['mo.md(\'[link](""") more\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # With bold/italic
    expected = wrap_generate_filecontents(
        ['mo.md(\'**bold """ text**\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Simplest case - space-separated triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\' """ \')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # With one char separator
    expected = wrap_generate_filecontents(
        ['mo.md(\'a"""b\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Alternating quote patterns
    expected = wrap_generate_filecontents(
        ['mo.md(\'Text " "" """ """\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Two quotes (not triple)
    expected = wrap_generate_filecontents(
        ["mo.md('Text with \"\" quotes')", "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Seven quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'Text with """"""" quotes\')', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # No space around triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'a"""b\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Space before only
    expected = wrap_generate_filecontents(
        ['mo.md(\'a """b\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Space after only
    expected = wrap_generate_filecontents(
        ['mo.md(\'a""" b\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Space both sides
    expected = wrap_generate_filecontents(
        ['mo.md(\'a """ b\')', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Using f-string single quotes with triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md(f\'value {x} with """\')', "import marimo as mo", "x = 1"],
        ["a", "b", "c"],
    )
    ast.parse(expected)  # should not raise

    # Using f-string double quotes with escaped triple quotes
    expected = wrap_generate_filecontents(
        [
            'mo.md(f"value {y} with \\"\\"\\" here")',
            "import marimo as mo",
            "y = 2",
        ],
        ["a", "b", "c"],
    )
    ast.parse(expected)  # should not raise

    # Using f-string triple quotes with escaped triple quotes
    expected = wrap_generate_filecontents(
        [
            'mo.md(f"""value {z} with \\"\\"\\" content""")',
            "import marimo as mo",
            "z = 3",
        ],
        ["a", "b", "c"],
    )
    ast.parse(expected)  # should not raise

    # f-string with multiple interpolations and triple quotes
    expected = wrap_generate_filecontents(
        [
            'mo.md(f"first {a} then \\"\\"\\" then {b}")',
            "import marimo as mo",
            "a = 1; b = 2",
        ],
        ["a", "b", "c"],
    )
    ast.parse(expected)  # should not raise

    # Raw f-string triple quotes with content
    expected = wrap_generate_filecontents(
        [
            'mo.md(fr"""raw {c} with \\"\\"\\" text""")',
            "import marimo as mo",
            "c = 4",
        ],
        ["a", "b", "c"],
    )
    ast.parse(expected)  # should not raise


def test_previous_problematic_cases() -> None:
    # All of these cases fail under 0.17.3 but should parse correctly now.
    # Bug resulting from mixed quote types.

    # Using double quotes with escaped triple quotes
    expected = wrap_generate_filecontents(
        ['mo.md("text with \\"\\"\\" here")', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Using triple quotes with escaped triple quotes inside
    expected = wrap_generate_filecontents(
        ['mo.md("""content with \\"\\"\\" inside""")', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # With lists
    expected = wrap_generate_filecontents(
        ['mo.md(\'- item with """\\n- another item\')', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Shell commands with quotes
    expected = wrap_generate_filecontents(
        ['mo.md(\'Run: echo """hello"""\\\'\')', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Quote blocks with triple quotes
    expected = wrap_generate_filecontents(
        [
            'mo.md(\'> Quote with """\\n> More content\')',
            "import marimo as mo",
        ],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise
    # Docstring examples in markdown
    expected = wrap_generate_filecontents(
        [
            'mo.md(\'Python docstrings use triple quotes:\\n"""\\nThis is a docstring\\n"""\')',
            "import marimo as mo",
        ],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Markdown with code blocks containing quotes
    expected = wrap_generate_filecontents(
        [
            'mo.md(\'```python\\nprint(""" hello """)\\n```\')',
            "import marimo as mo",
        ],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Triple quotes with newlines
    expected = wrap_generate_filecontents(
        ['mo.md(\'\\nline1 with """\\nline2\\n\')', "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Triple quotes with single quotes
    expected = wrap_generate_filecontents(
        ["mo.md('Text with \"\"\" and \\'single\\'')", "import marimo as mo"],
        ["a", "b"],
    )
    ast.parse(expected)  # should not raise

    # Double quotes with triple quotes at start
    expected = wrap_generate_filecontents(
        ['mo.md("\\"\\"\\" at start")', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise

    # Triple quotes with triple quotes at end
    expected = wrap_generate_filecontents(
        ['mo.md("""at end \\"\\"\\"""")', "import marimo as mo"], ["a", "b"]
    )
    ast.parse(expected)  # should not raise


def test_recover(tmp_path: Path) -> None:
    cells: NotebookV1 = {
        "version": "1",
        "metadata": {"marimo_version": __version__},
        "cells": [
            {"name": "a", "code": '"santa"\n\n"clause"\n\n\n'},
            {"name": "b", "code": ""},
            {"name": "c", "code": "\n123"},
        ],
    }
    filecontents = json.dumps(cells)
    # keep open for windows compat
    tempfile_name = tmp_path / "test.py"
    tempfile_name.write_text(filecontents)
    recovered = codegen.recover(tempfile_name)

    codes = [
        "\n".join(['"santa"', "", '"clause"', "", "", ""]),
        "",
        "\n".join(["", "123"]),
    ]
    names = ["a", "b", "c"]

    expected = wrap_generate_filecontents(codes, names)
    assert recovered == expected


# TODO(akshayka): more tests for attributes, classdefs, and closures
# TODO(akshayka): test builtin functions
# TODO(akshayka): test delete cell


def test_get_header_comments() -> None:
    filepath = get_filepath("test_get_header_comments")
    comments = codegen.get_header_comments(filepath)

    assert comments, "No comments found"
    assert '"""Docstring"""' in comments, "Docstring not found"
    assert '"""multi\n    line\n"""' in comments, "Multiline string not found"
    assert "# A copyright" in comments, "Comment not found"
    assert "# A linter" in comments, "Comment not found"


def test_get_header_comments_invalid() -> None:
    filepath = get_filepath("test_get_header_comments_invalid")
    comments = codegen.get_header_comments(filepath)

    assert comments is None, "Comments found when there should be none"


def test_sqls() -> None:
    code = dedent(
        """
    db.sql("SELECT * FROM foo")
    db.sql("ATTACH TABLE bar")
    """
    )
    cell = compile_cell(code)
    sqls = cell.sqls
    assert sqls == ["SELECT * FROM foo", "ATTACH TABLE bar"]


def test_is_internal_cell_name() -> None:
    assert is_internal_cell_name("__")
    assert is_internal_cell_name("_")
    assert not is_internal_cell_name("___")
    assert not is_internal_cell_name("__1213123123")
    assert not is_internal_cell_name("foo")


def test_format_tuple_elements() -> None:
    kv_case = codegen.format_tuple_elements(
        "@app.fn(...)",
        tuple(["a", "b", "c"]),
    )
    assert kv_case == "@app.fn(a, b, c)"

    indent_case = codegen.format_tuple_elements(
        "def fn(...):", tuple(["a", "b", "c"]), indent=True
    )
    assert indent_case == "    def fn(a, b, c):"

    multiline_case = codegen.format_tuple_elements(
        "return (...)",
        (
            "very",
            "long",
            "arglist",
            "that",
            "exceeds",
            "maximum",
            "characters",
            "for",
            "some",
            "reason",
            "or",
            "the",
            "other",
            "wowza",
        ),
        allowed_naked=True,
    )
    assert multiline_case == (
        "return (\n    "
        "very,\n    long,\n    arglist,\n    that,\n    exceeds,\n    maximum,\n"
        "    characters,\n    for,\n    some,\n    reason,\n"
        "    or,\n    the,\n    other,\n    wowza,\n)"
    )

    long_case = codegen.format_tuple_elements(
        "return (...)",
        (
            "very_long_name_that_exceeds_76_characters_for_some_reason_or_the_other_woowee",
        ),
        allowed_naked=True,
    )
    assert long_case == (
        "return (\n    "
        "very_long_name_that_exceeds_76_characters_for_some_reason_or_the_other_woowee,"
        "\n)"
    )
