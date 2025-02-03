from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from marimo._runtime.layout.layout import (
    LayoutConfig,
    read_layout_config,
    save_layout_config,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield tmp_dir


def test_save_layout_config(temp_dir: str):
    config = LayoutConfig(type="grid", data={"cols": 2})
    filepath = save_layout_config(temp_dir, "test.py", config)

    assert filepath == "layouts/test.grid.json"
    full_path = os.path.join(temp_dir, filepath)
    assert os.path.exists(full_path)

    with open(full_path) as f:
        saved_data = json.load(f)
    assert saved_data == {"type": "grid", "data": {"cols": 2}}


def test_read_layout_config(temp_dir: str):
    # Create a test layout file
    config = LayoutConfig(type="grid", data={"cols": 2})
    filepath = save_layout_config(temp_dir, "test.py", config)

    # Read it back
    read_config = read_layout_config(temp_dir, filepath)
    assert read_config is not None
    assert read_config.type == "grid"
    assert read_config.data == {"cols": 2}


def test_read_layout_config_data_uri():
    # Create a data URI
    config_data = {"type": "grid", "data": {"cols": 2}}
    json_str = json.dumps(config_data)
    import base64

    data_uri = f"data:application/json;base64,{base64.b64encode(json_str.encode()).decode()}"

    # Read it
    config = read_layout_config("", data_uri)
    assert config is not None
    assert config.type == "grid"
    assert config.data == {"cols": 2}


def test_read_layout_config_nonexistent_file(temp_dir: str):
    config = read_layout_config(temp_dir, "nonexistent.json")
    assert config is None


def test_read_layout_config_invalid_extension(temp_dir: str):
    # Create a non-JSON file
    path = Path(temp_dir) / "invalid.txt"
    path.write_text('{"type": "grid", "data": {}}')

    config = read_layout_config(temp_dir, "invalid.txt")
    assert config is None


def test_read_layout_config_invalid_data_uri():
    config = read_layout_config("", "data:invalid")
    assert config is None


def test_read_layout_config_invalid_json(temp_dir: str):
    # Create an invalid JSON file
    path = Path(temp_dir) / "layouts" / "invalid.grid.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text("invalid json")

    with pytest.raises(json.JSONDecodeError):
        read_layout_config(temp_dir, "layouts/invalid.grid.json")
