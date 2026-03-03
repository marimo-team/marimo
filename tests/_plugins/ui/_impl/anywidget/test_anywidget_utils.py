# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.anywidget.utils import extract_buffer_paths

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
