# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
import textwrap

import pytest

from marimo import _loggers
from marimo._ast import load
from marimo._ast.parse import MarimoFileError

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_filepath(name: str) -> str:
    return os.path.join(DIR_PATH, f"codegen_data/{name}.py")


@pytest.fixture
def static_load():
    return load._static_load


@pytest.fixture
def dynamic_load():
    return load._dynamic_load


@pytest.fixture(params=["static_load", "dynamic_load"])
def load_app(request):
    return request.getfixturevalue(request.param)


class TestGetCodes:
    @staticmethod
    def test_get_codes(load_app) -> None:
        app = load_app(get_filepath("test_generate_filecontents"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == [
            "one",
            "two",
            "three",
            "four",
            "five",
        ]
        assert list(cell_manager.codes()) == [
            "import numpy as np",
            "x = 0\nxx = 1",
            "y = x + 1",
            "# comment\nz = np.array(x + y)",
            "# just a comment",
        ]

    @staticmethod
    def test_get_codes_async(load_app) -> None:
        app = load_app(get_filepath("test_generate_filecontents_async"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == [
            "one",
            "two",
            "three",
        ]
        assert list(cell_manager.codes()) == [
            "import numpy as np\nimport asyncio",
            "x = 0\nxx = 1\nawait asyncio.sleep(1)",
            "async def _():\n    await asyncio.sleep(x)",
        ]

    @staticmethod
    def test_get_codes_with_incorrect_args_rets(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_with_incorrect_args_rets"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == [
            "one",
            "two",
            "three",
            "four",
            "five",
        ]
        assert list(cell_manager.codes()) == [
            "import numpy as np",
            "x = 0\nxx = 1",
            "y = x + 1",
            "# comment\nz = np.array(x + y)",
            "# just a comment\n...",
        ]

    @staticmethod
    def test_get_codes_with_name_error(load_app) -> None:
        # name mo is not defined --- make sure this file is still parseable
        app = load_app(get_filepath("test_get_codes_with_name_error"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == [
            "mo",
        ]

    @staticmethod
    def test_get_codes_multiline_fndef(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_multiline_fndef"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == [
            "# comment\nx = 0 + a + b + c + d",
        ]

    @staticmethod
    def test_get_codes_messy(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_messy"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["__"]
        assert list(cell_manager.codes()) == [
            "# comment\n# another comment\n\n# yet another comment\n"
            + "x = 0 + a + b + c + d",
        ]

    @staticmethod
    def test_get_setup(load_app) -> None:
        app = load_app(get_filepath("test_get_setup"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["setup", "*fn"]
        assert list(cell_manager.codes()) == [
            "variable = 1",
            textwrap.dedent(
                """\
                def fn(x: int):
                    return x + variable"""
            ),
        ]

    @staticmethod
    def test_get_setup_blank(load_app) -> None:
        app = load_app(get_filepath("test_get_setup_blank"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["setup", "*fn"]
        assert list(cell_manager.codes()) == [
            "# Only comments\n# and a pass",
            textwrap.dedent(
                """\
                def fn(x: int):
                    return x + variable"""
            ),
        ]

    @staticmethod
    def test_get_codes_messy_toplevel(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_messy_toplevel"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["*fn", "wrapped"]
        assert list(cell_manager.codes()) == [
            "def fn(a,\n        b, #   hello,\n        c,    # again\n        d,) -> int:\n"
            + "    # comment\n    # another comment\n\n    # yet another comment\n"
            + "    return 0 + a + b + c + d",
            "",
        ]

    @staticmethod
    def test_get_codes_single_line_fn(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_single_line_fn"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one", "two"]
        assert list(cell_manager.codes()) == ["c = a + b; print(c); ", "..."]

    @staticmethod
    def test_get_codes_multiline_string(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_multiline_string"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one", "two"]
        assert list(cell_manager.codes()) == [
            'c = """\n  a, b"""; ',
            'd = """\na, b"""\n# comment',
        ]

    @staticmethod
    def test_get_codes_comment_after_sig(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_comment_after_sig"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ['print("hi")']

    @staticmethod
    def test_get_codes_empty(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_empty"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one", "two", "three", "four"]
        assert [c.strip() for c in cell_manager.codes()] == ["", "", "", ""]

    @staticmethod
    def test_get_codes_syntax_error(load_app) -> None:
        app = load_app(
            get_filepath("test_generate_filecontents_with_syntax_error")
        )
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one", "two", "_", "_"]
        assert list(cell_manager.codes()) == [
            "import numpy as np",
            "_ error",
            "'all good'",
            '_ another_error\n_ and """another"""\n\n    \\t',
        ]

    @staticmethod
    def test_get_codes_app_with_only_comments(load_app) -> None:
        app = load_app(get_filepath("test_app_with_only_comments"))
        assert app is None

    @staticmethod
    def test_get_codes_non_marimo_python_script(static_load) -> None:
        with pytest.raises(MarimoFileError, match="is not a marimo notebook."):
            static_load(
                get_filepath("test_get_codes_non_marimo_python_script")
            )

    @staticmethod
    def test_import_alias(static_load) -> None:
        app = static_load(get_filepath("test_get_alias_import"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]

    @staticmethod
    def test_get_codes_app_with_no_cells(load_app) -> None:
        app = load_app(get_filepath("test_app_with_no_cells"))
        assert app is not None
        app._cell_manager.ensure_one_cell()
        assert list(app._cell_manager.names()) == ["_"]
        assert list(app._cell_manager.codes()) == [""]

    @staticmethod
    def test_get_codes_toplevel(load_app) -> None:
        app = load_app(get_filepath("test_generate_filecontents_toplevel"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == [
            "setup",
            "_",
            "*addition",
            "*shadow_case",
            "_",
            "_",
            "*fun_that_uses_mo",
            "*fun_that_uses_another_but_out_of_order",
            "*fun_uses_file",
            "*fun_that_uses_another",
            "cell_with_ref_and_def",
            "_",
            "*ExampleClass",
            "*SubClass",
        ]

    @staticmethod
    def test_get_app_kwargs(load_app) -> None:
        app = load_app(get_filepath("test_get_app_kwargs"))
        assert app is not None
        assert app._filename.endswith("test_get_app_kwargs.py")
        assert app._config.layout_file == "layouts/layout.json"
        assert app._config.app_title == "title"
        assert app._config.auto_download == "html"

    @staticmethod
    def test_get_bad_kwargs(load_app, caplog) -> None:
        # Should be stderr since warn level
        with caplog.at_level(logging.WARNING):
            _loggers.marimo_logger().propagate = True
            app = load_app(get_filepath("test_get_bad_kwargs"))
            assert app is not None

        # Don't worry about the discrepancy since dynamic_load should not be in
        # prod.
        if load_app == load._static_load:
            assert len(caplog.records) == 2
            assert "fake_kwarg" in caplog.text
        else:
            assert len(caplog.records) == 1
        assert "kwarg_that_doesnt_exist" in caplog.text

    @staticmethod
    def test_get_app_with_decorator(static_load) -> None:
        app = static_load(get_filepath("test_with_decorator"))
        assert app is not None
        assert app._cell_manager.get_cell_data_by_name("wrap").cell.defs == {
            "wrap"
        }
        assert app._cell_manager.get_cell_data_by_name(
            "hundred"
        ).cell.defs == {"hundred"}
        from codegen_data.test_with_decorator import hundred

        assert hundred == 100


class TestGetStatus:
    @staticmethod
    @pytest.mark.parametrize(
        ("filename", "expected_status"),
        [
            # Valid marimo apps
            ("test_main", "valid"),
            ("test_generate_filecontents", "valid"),
            ("test_generate_filecontents_async", "valid"),
            ("test_generate_filecontents_async_long_signature", "valid"),
            ("test_generate_filecontents_single_cell", "valid"),
            ("test_generate_filecontents_toplevel", "valid"),
            ("test_generate_filecontents_toplevel_pytest", "valid"),
            ("test_get_codes_multiline_string", "valid"),
            ("test_get_codes_messy", "valid"),
            ("test_get_codes_single_line_fn", "valid"),
            ("test_get_codes_multiline_fndef", "valid"),
            ("test_get_codes_comment_after_sig", "valid"),
            ("test_get_codes_empty", "valid"),
            ("test_get_header_comments", "valid"),
            ("test_get_setup", "valid"),
            ("test_get_setup_blank", "valid"),
            ("test_generate_filecontents_shadowed_builtin", "valid"),
            ("test_generate_filecontents_unshadowed_builtin", "valid"),
            ("test_app_with_annotation_typing", "valid"),
            ("test_long_line_in_main", "valid"),
            ("test_with_decorator", "valid"),
            # Potentially confusing but valid
            ("test_get_codes_with_name_error", "valid"),  # runtime error
            ("test_syntax_errors", "valid"),  # runtime syntax errors
            # Broken signature, but fine otherwise
            ("test_get_codes_with_incorrect_args_rets", "valid"),
            # unparse cells
            ("test_generate_filecontents_with_syntax_error", "valid"),
            # Empty files
            ("test_empty", "empty"),
            # No cells
            ("test_app_with_only_comments", "invalid"),
            # Invalid (not marimo apps)
            ("test_invalid", "invalid"),
            # Has errors
            ("test_get_codes_messy_toplevel", "has_errors"),
            ("test_get_header_comments_invalid", "has_errors"),
            ("test_get_bad_kwargs", "has_errors"),
            # Unparsable
            (
                "test_get_codes_non_marimo_python_script",
                "invalid",
            ),  # not marimo
            # Potentially confusing and has_errors
            ("test_get_alias_import", "has_errors"),  # not official format
            ("test_get_app_kwargs", "has_errors"),  # Intentionally bad kwargs
            # Empty files can still be opened.
            (
                "test_generate_filecontents_empty_with_config",
                "has_errors",
            ),  # no body
            ("test_generate_filecontents_empty", "has_errors"),  # no body
            ("test_app_with_no_cells", "has_errors"),  # No body is an error
            # Invalid decorator order creates an error.
            ("test_decorators", "has_errors"),
            # Syntax errors in code
            ("_test_not_parsable", "broken"),
            ("_test_parse_error_in_notebook", "broken"),
            # A script that is not a marimo notebook, but uses marimo is
            # indeterminant, so throws an exception.
            ("test_non_marimo", "broken"),
        ],
    )
    def test_get_status(filename: str, expected_status: str) -> None:
        if expected_status == "broken":
            with pytest.raises((MarimoFileError, SyntaxError)):
                load.get_notebook_status(get_filepath(filename))
            return

        assert (
            load.get_notebook_status(get_filepath(filename)).status
            == expected_status
        )
