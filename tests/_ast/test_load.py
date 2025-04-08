# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os

from marimo._ast import load

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_filepath(name: str) -> str:
    return os.path.join(DIR_PATH, f"codegen_data/{name}.py")


class TestGetCodes:
    @staticmethod
    def test_get_codes() -> None:
        app = load.load_app(get_filepath("test_generate_filecontents"))
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
    def test_get_codes_async() -> None:
        app = load.load_app(get_filepath("test_generate_filecontents_async"))
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
    def test_get_codes_with_incorrect_args_rets() -> None:
        app = load.load_app(
            get_filepath("test_get_codes_with_incorrect_args_rets")
        )
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
    def test_get_codes_with_name_error() -> None:
        # name mo is not defined --- make sure this file is still parseable
        app = load.load_app(get_filepath("test_get_codes_with_name_error"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == [
            "mo",
        ]

    @staticmethod
    def test_get_codes_multiline_fndef() -> None:
        app = load.load_app(get_filepath("test_get_codes_multiline_fndef"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == [
            "# comment\nx = 0 + a + b + c + d",
        ]

    @staticmethod
    def test_get_codes_messy() -> None:
        app = load.load_app(get_filepath("test_get_codes_messy"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["__"]
        assert list(cell_manager.codes()) == [
            "# comment\n# another comment\n\n# yet another comment\n"
            + "x = 0 + a + b + c + d",
        ]

    @staticmethod
    def test_get_codes_single_line_fn() -> None:
        app = load.load_app(get_filepath("test_get_codes_single_line_fn"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ["c = a + b; print(c); "]

    @staticmethod
    def test_get_codes_multiline_string() -> None:
        app = load.load_app(get_filepath("test_get_codes_multiline_string"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ['c = """\n  a, b"""; ']

    @staticmethod
    def test_get_codes_comment_after_sig() -> None:
        app = load.load_app(get_filepath("test_get_codes_comment_after_sig"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ['print("hi")']

    @staticmethod
    def test_get_codes_empty() -> None:
        app = load.load_app(get_filepath("test_get_codes_empty"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one", "two"]
        assert [c.strip() for c in cell_manager.codes()] == ["", ""]

    @staticmethod
    def test_get_codes_syntax_error() -> None:
        app = load.load_app(
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
    def test_get_codes_app_with_only_comments() -> None:
        app = load.load_app(get_filepath("test_app_with_only_comments"))
        assert app is None

    @staticmethod
    def test_get_codes_app_with_no_cells() -> None:
        app = load.load_app(get_filepath("test_app_with_no_cells"))
        assert app is not None
        app._cell_manager.ensure_one_cell()
        assert list(app._cell_manager.names()) == ["_"]
        assert list(app._cell_manager.codes()) == [""]
