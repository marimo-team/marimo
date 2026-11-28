# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._core.result import Err, Ok, Result


@pytest.mark.parametrize(
    ("result", "field"), [(Ok("value"), "value"), (Err("error"), "error")]
)
def test_payload_is_read_only(result: Result[str, str], field: str) -> None:
    with pytest.raises(AttributeError):
        setattr(result, field, 1)
