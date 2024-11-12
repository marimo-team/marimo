# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import re
from pathlib import Path

import pytest

from marimo._convert.ipynb import convert_from_ipynb
from tests.mocks import snapshotter

snapshot = snapshotter(__file__)

DIR_PATH = Path(__file__).parent / "ipynb_data"


@pytest.mark.parametrize("ipynb_path", DIR_PATH.glob("*.ipynb.txt"))
def test_ipynb_to_marimo_snapshots(ipynb_path: Path) -> None:
    contents = ipynb_path.read_text()
    converted = convert_from_ipynb(contents)
    converted = re.sub(r"__generated_with = .*\n", "", converted)
    converted = re.sub(r"# requires-python = .*\n", "", converted)
    snapshot(
        f"converted_{ipynb_path.name.replace('.ipynb.txt', '.py.txt')}",
        converted,
    )
