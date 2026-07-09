# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._utils.assert_never import assert_never, log_never


def test_assert_never_raises_with_value_and_type():
    with pytest.raises(AssertionError) as exc_info:
        assert_never("hello")
    message = str(exc_info.value)
    assert "hello" in message
    assert "str" in message


def test_assert_never_reports_the_type_name():
    with pytest.raises(AssertionError, match=r"Unhandled value: 5 \(int\)"):
        assert_never(5)


def test_log_never_returns_none_without_raising():
    # log_never is the non-fatal counterpart: it logs a warning instead of
    # raising, and returns None.
    assert log_never(42) is None
