# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._utils.timer import timer


def test_timer_returns_wrapped_result():
    @timer
    def add(a, b, c=0):
        return a + b + c

    assert add(2, 3, c=4) == 9


def test_timer_forwards_args_and_kwargs():
    received = {}

    @timer
    def record(*args: object, **kwargs: object) -> None:
        received["args"] = args
        received["kwargs"] = kwargs

    record(1, 2, key="value")
    assert received["args"] == (1, 2)
    assert received["kwargs"] == {"key": "value"}


def test_timer_preserves_metadata():
    @timer
    def original():
        """my docstring"""

    assert original.__name__ == "original"
    assert original.__doc__ == "my docstring"


def test_timer_prints_timing(capsys):
    @timer
    def work():
        return 1

    work()
    out = capsys.readouterr().out
    assert "work took" in out
    assert "seconds to execute" in out
