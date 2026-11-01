# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pathlib

from marimo._utils.config.config import ConfigReader


def test_read_toml_falls_back_on_invalid_utf8(tmp_path: pathlib.Path) -> None:
    """A state file with non-UTF-8 bytes is unreadable, not fatal.

    Windows writes the state file with the system locale, so a Chinese
    username can leave 0xbf bytes in it and every read raised
    UnicodeDecodeError out of the homepage.
    """
    state = tmp_path / "recent_files.toml"
    state.write_bytes(
        b'files = ["C:/Users/' + bytes([0xBF, 0xBF]) + b'/a.py"]\n'
    )

    reader = ConfigReader(state)

    assert reader.read_toml(dict, fallback={"files": []}) == {"files": []}


def test_read_toml_still_reads_a_valid_file(tmp_path: pathlib.Path) -> None:
    state = tmp_path / "recent_files.toml"
    state.write_text('files = ["a.py"]\n', encoding="utf-8")

    reader = ConfigReader(state)

    assert reader.read_toml(dict, fallback={"files": []}) == {
        "files": ["a.py"]
    }
