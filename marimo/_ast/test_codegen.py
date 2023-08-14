# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import json
import os
import tempfile
from inspect import cleandoc

from marimo import __version__
from marimo._ast import codegen
from marimo._ast.cell import parse_cell

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_expected_filecontents(name: str) -> str:
    with open(
        os.path.join(DIR_PATH, f"../_test_utils/codegen_data/{name}.py"), "r"
    ) as f:
        contents = f.read()
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


def get_filepath(name: str) -> str:
    return os.path.join(DIR_PATH, f"../_test_utils/codegen_data/{name}.py")


class TestGeneration:
    @staticmethod
    def test_generate_filecontents() -> None:
        cell_one = "import numpy as np"
        cell_two = "x = 0\nxx = 1"
        cell_three = "y = x + 1"
        cell_four = "# comment\nz = np.array(x + y)"
        cell_five = "# just a comment"
        codes = [cell_one, cell_two, cell_three, cell_four, cell_five]
        names = ["one", "two", "three", "four", "five"]
        contents = codegen.generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents"
        )

    @staticmethod
    def test_generate_filecontents_single_cell() -> None:
        cell_one = "import numpy as np"
        codes = [cell_one]
        names = ["one"]
        contents = codegen.generate_filecontents(codes, names)
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
        contents = codegen.generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_with_syntax_error"
        )

    @staticmethod
    def test_generate_unparseable_cell() -> None:
        code = "    error\n\\t"
        raw = codegen.generate_unparseable_cell(code, None)
        print(raw)
        stringified = eval("\n".join(raw.split("\n")[1:5])).split("\n")
        print(stringified)
        # first line empty
        assert not stringified[0]
        # leading 4 spaces followed by source line
        assert stringified[1] == " " * 4 + "    error"
        # leading 4 spaces followed by source line
        assert stringified[2] == " " * 4 + "\\t"
        # leading 4 spaces followed by nothing
        assert stringified[3] == " " * 4

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
        contents = codegen.generate_filecontents(
            [cell_one, cell_two], ["one", "two"]
        )
        assert contents == get_expected_filecontents("test_long_line_in_main")

    @staticmethod
    def test_generate_filecontents_unshadowed_builtin() -> None:
        cell_one = "type"
        codes = [cell_one]
        names = ["one"]
        contents = codegen.generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_unshadowed_builtin"
        )

    @staticmethod
    def test_generate_filecontents_shadowed_builtin() -> None:
        cell_one = "type = 1"
        cell_two = "type"
        codes = [cell_one, cell_two]
        names = ["one", "two"]
        contents = codegen.generate_filecontents(codes, names)
        assert contents == get_expected_filecontents(
            "test_generate_filecontents_shadowed_builtin"
        )


class TestGetCodes:
    @staticmethod
    def test_get_codes() -> None:
        codes, names = codegen.get_codes(
            get_filepath("test_generate_filecontents")
        )
        assert names == ["one", "two", "three", "four", "five"]
        assert codes == [
            "import numpy as np",
            "x = 0\nxx = 1",
            "y = x + 1",
            "# comment\nz = np.array(x + y)",
            "# just a comment",
        ]

    @staticmethod
    def test_get_codes_with_name_error() -> None:
        # name mo is not defined --- make sure this file is still parseable
        codes, names = codegen.get_codes(
            get_filepath("test_get_codes_with_name_error")
        )
        assert names == ["one"]
        assert codes == [
            "mo",
        ]

    @staticmethod
    def test_get_codes_multiline_fndef() -> None:
        codes, names = codegen.get_codes(
            get_filepath("test_get_codes_multiline_fndef")
        )
        assert names == ["one"]
        assert codes == [
            "# comment\nx = 0 + a + b + c + d",
        ]

    @staticmethod
    def test_get_codes_messy() -> None:
        codes, names = codegen.get_codes(get_filepath("test_get_codes_messy"))
        assert names == ["__"]
        assert codes == [
            "# comment\n# another comment\n\n# yet another comment\n"
            + "x = 0 + a + b + c + d",
        ]

    @staticmethod
    def test_get_codes_single_line_fn() -> None:
        codes, names = codegen.get_codes(
            get_filepath("test_get_codes_single_line_fn")
        )
        assert names == ["one"]
        assert codes == ["c = a + b; print(c); "]

    @staticmethod
    def test_get_codes_multiline_string() -> None:
        codes, names = codegen.get_codes(
            get_filepath("test_get_codes_multiline_string")
        )
        assert names == ["one"]
        assert codes == ['c = """\n  a, b"""; ']

    @staticmethod
    def test_get_codes_comment_after_sig() -> None:
        codes, names = codegen.get_codes(
            get_filepath("test_get_codes_comment_after_sig")
        )
        assert names == ["one"]
        assert codes == ['print("hi")']

    @staticmethod
    def test_get_codes_empty() -> None:
        codes, names = codegen.get_codes(get_filepath("test_get_codes_empty"))
        assert names == ["one", "two"]
        assert [c.strip() for c in codes] == ["", ""]

    @staticmethod
    def test_get_codes_syntax_error() -> None:
        codes, names = codegen.get_codes(
            get_filepath("test_generate_filecontents_with_syntax_error")
        )
        assert names == ["one", "two", "__", "__"]
        assert codes == [
            "import numpy as np",
            "_ error",
            "'all good'",
            '_ another_error\n_ and """another"""\n\n    \\t',
        ]


class TestApp:
    @staticmethod
    def test_run() -> None:
        import marimo._test_utils.codegen_data.test_main as mod

        outputs, defs = mod.app.run()
        assert outputs == (None, "z", None)
        assert defs == {"x": 0, "y": 1, "z": 2, "a": 1}


class TestToFunctionDef:
    def test_tofunctiondef_one_def(self) -> None:
        code = "x = 0"
        cell = parse_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo():", "    x = 0", "    return x,"]
        )
        assert fndef == expected

    def test_tofunctiondef_one_ref(self) -> None:
        code = "y + 1"
        cell = parse_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo(y):", "    y + 1", "    return"]
        )
        assert fndef == expected

    def test_tofunctiondef_empty_cells(self) -> None:
        code = ""
        cell = parse_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(["@app.cell", "def foo():", "    return"])

        code = "\n #\n"
        cell = parse_cell(code)
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
        cell = parse_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo(y):", "    print(y)", "    return"]
        )
        assert fndef == expected

    def test_tofunctiondef_refs_and_defs(self) -> None:
        code = "\n".join(["y = x", "z = x", "z = w + y"])
        cell = parse_cell(code)
        fndef = codegen.to_functiondef(cell, "foo")
        expected = "\n".join(
            ["@app.cell", "def foo(w, x):"]
            + ["    " + line for line in code.split("\n")]
            + ["    return y, z"]
        )
        assert fndef == expected


def test_recover() -> None:
    cells = {
        "cells": [
            {"name": "a", "code": '"santa"\n\n"claus"\n\n\n'},
            {"name": "b", "code": ""},
            {"name": "c", "code": "\n123"},
        ]
    }
    filecontents = json.dumps(cells)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py") as f:
        f.write(filecontents)
        f.seek(0)
        recovered = codegen.recover(f.name)

    codes = [
        "\n".join(['"santa"', "", '"claus"', "", "", ""]),
        "",
        "\n".join(["", "123"]),
    ]
    names = ["a", "b", "c"]

    expected = codegen.generate_filecontents(codes, names)
    assert recovered == expected


# TODO(akshayka): more tests for attributes, classdefs, and closures
# TODO(akshayka): test builtin functions
# TODO(akshayka): test delete cell
