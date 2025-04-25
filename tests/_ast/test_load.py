# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import logging
import os
import textwrap

import pytest

from marimo import _loggers
from marimo._ast import load

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
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ["c = a + b; print(c); "]

    @staticmethod
    def test_get_codes_multiline_string(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_multiline_string"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ['c = """\n  a, b"""; ']

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
