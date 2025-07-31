# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.anywidget.utils import (
    extract_buffer_paths,
    insert_buffer_paths,
    is_model_message,
)

HAS_DEPS = DependencyManager.ipywidgets.has()


@pytest.mark.skipif(not HAS_DEPS, reason="ipywidgets is not installed")
def test_extract_buffer_paths():
    # Test with a simple message containing buffers
    message = {
        "method": "update",
        "state": {"value": b"test", "other": "not a buffer"},
        "buffer_paths": [["state", "value"]],
    }

    state, buffer_paths, buffers = extract_buffer_paths(message["state"])

    assert isinstance(state, dict)
    assert isinstance(buffer_paths, list)
    assert isinstance(buffers, list)
    assert len(buffers) == 1
    assert buffers[0] == b"test"
    assert state["other"] == "not a buffer"
    assert "value" not in state


@pytest.mark.skipif(not HAS_DEPS, reason="ipywidgets is not installed")
def test_insert_buffer_paths():
    # Test inserting buffers back into state
    state = {"method": "update", "state": {"other": "not a buffer"}}
    buffer_paths = [["state", "value"]]
    buffers = [b"test"]

    result = insert_buffer_paths(state, buffer_paths, buffers)

    assert isinstance(result, dict)
    assert result["state"]["value"] == b"test"
    assert result["state"]["other"] == "not a buffer"


@pytest.mark.skipif(not HAS_DEPS, reason="ipywidgets is not installed")
def test_is_model_message():
    # Test valid model message
    valid_message = {
        "method": "update",
        "state": {"value": "test"},
        "buffer_paths": [],
    }
    assert is_model_message(valid_message) is True

    # Test invalid messages
    assert is_model_message({}) is False
    assert is_model_message({"method": "update"}) is False
    assert is_model_message({"state": {}, "buffer_paths": []}) is False
    assert is_model_message(None) is False
    assert is_model_message("not a dict") is False
