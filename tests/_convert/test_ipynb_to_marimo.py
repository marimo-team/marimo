# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from pathlib import Path

import pytest

from marimo._convert.converters import MarimoConvert
from marimo._convert.ipynb import convert_from_ipynb_to_notebook_ir
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)

DIR_PATH = Path(__file__).parent / "ipynb_data"


@pytest.mark.parametrize("ipynb_path", DIR_PATH.glob("*.ipynb.txt"))
def test_ipynb_to_marimo_snapshots(ipynb_path: Path) -> None:
    contents = ipynb_path.read_text()
    ir = convert_from_ipynb_to_notebook_ir(contents)
    converted = MarimoConvert.from_ir(ir).to_py()

    converted = re.sub(r"__generated_with = .*\n", "", converted)
    converted = re.sub(r"# requires-python = .*\n", "", converted)
    snapshot(
        f"converted_{ipynb_path.name.replace('.ipynb.txt', '.py.txt')}",
        converted,
    )
