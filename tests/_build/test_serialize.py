# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from marimo._build.serialize import classify_value, write_artifact

if TYPE_CHECKING:
    from pathlib import Path

pl = pytest.importorskip("polars")


def test_classify_dataframe() -> None:
    df = pl.DataFrame({"x": [1, 2, 3]})
    assert classify_value(df) == "dataframe"


def test_classify_json_primitives() -> None:
    assert classify_value({"k": [1, 2]}) == "json"
    assert classify_value([1, 2, 3]) == "json"
    assert classify_value("hi") == "json"
    assert classify_value(42) == "json"


def test_classify_unknown_returns_none() -> None:
    class _NotSerializable:
        pass

    assert classify_value(_NotSerializable()) is None
    assert classify_value({1, 2}) is None


def test_write_dataframe(tmp_path: Path) -> None:
    df = pl.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]})
    out = tmp_path / "df.parquet"
    write_artifact(df, out, "dataframe")
    assert out.exists()
    roundtrip = pl.read_parquet(out)
    assert roundtrip.equals(df)


def test_write_json(tmp_path: Path) -> None:
    out = tmp_path / "value.json"
    value = {"key": [1, 2], "nested": {"x": 3}}
    write_artifact(value, out, "json")
    assert json.loads(out.read_text()) == value


def test_write_creates_parent_dir(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir" / "value.json"
    write_artifact({"a": 1}, out, "json")
    assert out.exists()
