# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pickle
import traceback

import pytest
from inline_snapshot import snapshot

from marimo._core.errors import InternalError


def test_internal_error_survives_serialization() -> None:
    error = InternalError("Cell is not initialized")
    restored = pickle.loads(pickle.dumps(error))

    assert isinstance(restored, RuntimeError)
    assert restored.args == error.args
    assert (
        str(restored)
        == str(error)
        == snapshot(
            "Cell is not initialized\n\n"
            "This is an internal marimo error. Please report it at "
            "https://github.com/marimo-team/marimo/issues "
            "and include the full traceback."
        )
    )


def test_internal_error_preserves_traceback_and_cause() -> None:
    def fail() -> None:
        try:
            raise ValueError("Original failure")
        except ValueError as cause:
            raise InternalError("Cell is not initialized") from cause

    with pytest.raises(InternalError) as exc_info:
        fail()

    rendered = "".join(traceback.format_exception(exc_info.value))
    assert "ValueError: Original failure" in rendered
    assert (
        'raise InternalError("Cell is not initialized") from cause' in rendered
    )
    assert rendered.endswith(f"{exc_info.value}\n")
    assert rendered.count("https://github.com/marimo-team/marimo/issues") == 1
