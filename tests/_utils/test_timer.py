# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from marimo._utils.timer import timer

if TYPE_CHECKING:
    import pytest


def test_timer(capsys: pytest.CaptureFixture[str]) -> None:
    @timer
    def append(values: list[int], /, *, value: int) -> list[int]:
        values.append(value)
        return values

    values = [1]
    with patch("marimo._utils.timer.time.perf_counter", side_effect=[1, 1.25]):
        result = append(values, value=2)

    assert result is values
    assert result == [1, 2]
    assert append.__name__ == "append"
    assert capsys.readouterr().out == "append took 0.2500 seconds to execute\n"
