# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

import os

<<<<<<< HEAD
=======
import pytest

>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
from marimo._ast import load

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_filepath(name: str) -> str:
    return os.path.join(DIR_PATH, f"codegen_data/{name}.py")


<<<<<<< HEAD
class TestGetCodes:
    @staticmethod
    def test_get_codes() -> None:
        app = load.load_app(get_filepath("test_generate_filecontents"))
=======
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
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
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
<<<<<<< HEAD
    def test_get_codes_async() -> None:
        app = load.load_app(get_filepath("test_generate_filecontents_async"))
=======
    def test_get_codes_async(load_app) -> None:
        app = load_app(get_filepath("test_generate_filecontents_async"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
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
<<<<<<< HEAD
    def test_get_codes_with_incorrect_args_rets() -> None:
        app = load.load_app(
            get_filepath("test_get_codes_with_incorrect_args_rets")
        )
=======
    def test_get_codes_with_incorrect_args_rets(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_with_incorrect_args_rets"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
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
<<<<<<< HEAD
    def test_get_codes_with_name_error() -> None:
        # name mo is not defined --- make sure this file is still parseable
        app = load.load_app(get_filepath("test_get_codes_with_name_error"))
=======
    def test_get_codes_with_name_error(load_app) -> None:
        # name mo is not defined --- make sure this file is still parseable
        app = load_app(get_filepath("test_get_codes_with_name_error"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == [
            "mo",
        ]

    @staticmethod
<<<<<<< HEAD
    def test_get_codes_multiline_fndef() -> None:
        app = load.load_app(get_filepath("test_get_codes_multiline_fndef"))
=======
    def test_get_codes_multiline_fndef(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_multiline_fndef"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == [
            "# comment\nx = 0 + a + b + c + d",
        ]

    @staticmethod
<<<<<<< HEAD
    def test_get_codes_messy() -> None:
        app = load.load_app(get_filepath("test_get_codes_messy"))
=======
    def test_get_codes_messy(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_messy"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["__"]
        assert list(cell_manager.codes()) == [
            "# comment\n# another comment\n\n# yet another comment\n"
            + "x = 0 + a + b + c + d",
        ]

    @staticmethod
<<<<<<< HEAD
    def test_get_codes_single_line_fn() -> None:
        app = load.load_app(get_filepath("test_get_codes_single_line_fn"))
=======
    def test_get_codes_messy_toplevel(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_messy_toplevel"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["fn", "wrapped"]
        assert list(cell_manager.codes()) == [
            "def fn(a,\n        b, #   hello,\n        c,    # again\n        d,) -> int:\n"
            + "    # comment\n    # another comment\n\n    # yet another comment\n"
            + "    return 0 + a + b + c + d",
            "",
        ]

    @staticmethod
    def test_get_codes_single_line_fn(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_single_line_fn"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ["c = a + b; print(c); "]

    @staticmethod
<<<<<<< HEAD
    def test_get_codes_multiline_string() -> None:
        app = load.load_app(get_filepath("test_get_codes_multiline_string"))
=======
    def test_get_codes_multiline_string(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_multiline_string"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ['c = """\n  a, b"""; ']

    @staticmethod
<<<<<<< HEAD
    def test_get_codes_comment_after_sig() -> None:
        app = load.load_app(get_filepath("test_get_codes_comment_after_sig"))
=======
    def test_get_codes_comment_after_sig(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_comment_after_sig"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one"]
        assert list(cell_manager.codes()) == ['print("hi")']

    @staticmethod
<<<<<<< HEAD
    def test_get_codes_empty() -> None:
        app = load.load_app(get_filepath("test_get_codes_empty"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one", "two"]
        assert [c.strip() for c in cell_manager.codes()] == ["", ""]

    @staticmethod
    def test_get_codes_syntax_error() -> None:
        app = load.load_app(
=======
    def test_get_codes_empty(load_app) -> None:
        app = load_app(get_filepath("test_get_codes_empty"))
        assert app is not None
        cell_manager = app._cell_manager
        assert list(cell_manager.names()) == ["one", "two", "three", "four"]
        assert [c.strip() for c in cell_manager.codes()] == ["", "", "", ""]

    @staticmethod
    def test_get_codes_syntax_error(load_app) -> None:
        app = load_app(
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
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
<<<<<<< HEAD
    def test_get_codes_app_with_only_comments() -> None:
        app = load.load_app(get_filepath("test_app_with_only_comments"))
        assert app is None

    @staticmethod
    def test_get_codes_app_with_no_cells() -> None:
        app = load.load_app(get_filepath("test_app_with_no_cells"))
=======
    def test_get_codes_app_with_only_comments(load_app) -> None:
        app = load_app(get_filepath("test_app_with_only_comments"))
        assert app is None

    @staticmethod
    def test_get_codes_app_with_no_cells(load_app) -> None:
        app = load_app(get_filepath("test_app_with_no_cells"))
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
        assert app is not None
        app._cell_manager.ensure_one_cell()
        assert list(app._cell_manager.names()) == ["_"]
        assert list(app._cell_manager.codes()) == [""]
<<<<<<< HEAD
=======

    @staticmethod
    def test_get_codes_toplevel(load_app) -> None:
        app = load_app(get_filepath("test_generate_filecontents_toplevel"))
        assert app is not None
>>>>>>> 86b96e5324642142eabda3d8510d93e4321d3267
