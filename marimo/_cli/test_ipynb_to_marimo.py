# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import os
import tempfile
import textwrap
from collections.abc import Sequence

from marimo._ast import codegen
from marimo._cli.ipynb_to_marimo import convert

DIR_PATH = os.path.dirname(os.path.realpath(__file__))


def get_codes(ipynb_name: str) -> tuple[Sequence[str], Sequence[str]]:
    contents = convert(
        DIR_PATH + f"/../_test_utils/ipynb_data/{ipynb_name}.ipynb.txt"
    )

    tempfile_name = ""
    try:
        # in windows, can't re-open an open named temporary file, hence
        # delete=False and manual clean up
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            tempfile_name = f.name
            f.write(contents)
            f.seek(0)
        app = codegen.get_app(f.name)
        assert app is not None
        return list(app._codes()), list(app._names())
    finally:
        os.remove(tempfile_name)


def test_markdown() -> None:
    codes, names = get_codes("markdown")

    assert len(codes) == 3
    assert (
        codes[0]
        == textwrap.dedent(
            """
            mo.md(
                \"\"\"
                # Hello, markdown

                \\"\\"\\"
                'hello"
                '''
                \\"\\"\\"
                \"\"\"
            )
            """
        ).strip()
    )
    assert (
        codes[1]
        == textwrap.dedent(
            """
            mo.md(
                \"\"\"
                Here is some math

                $x = 0$
                \"\"\"
            )
            """
        ).strip()
    )
    assert codes[2] == "import marimo as mo"
    assert [name == "_" for name in names]


def test_arithmetic() -> None:
    codes, names = get_codes("arithmetic")

    assert len(codes) == 2
    assert codes[0] == "x = 0\nx"
    assert codes[1] == "x + 1"
    assert names == ["_", "_"]


def test_blank() -> None:
    codes, names = get_codes("blank")

    assert len(codes) == 1
    assert codes[0] == ""
    assert names == ["_"]


def test_unparsable() -> None:
    codes, names = get_codes("unparsable")

    assert len(codes) == 2
    assert codes[0] == "!echo hello, world\n\nx = 0"
    assert codes[1] == "x"
    assert names == ["_", "_"]
