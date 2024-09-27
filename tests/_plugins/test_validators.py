from __future__ import annotations

import warnings

import pytest

from marimo._plugins.validators import (
    validate_between_range,
    validate_number,
    validate_range,
    warn_js_safe_number,
)


def test_validate_range():
    # Valid ranges
    validate_range(0, 10)
    validate_range(-10, 10)
    validate_range(0.5, 1.5)
    validate_range(None, 10)
    validate_range(0, None)
    validate_range(None, None)

    # Invalid ranges
    with pytest.raises(
        ValueError, match="min/start must be less than or equal to max/end"
    ):
        validate_range(10, 0)

    with pytest.raises(
        ValueError, match="min/start must be less than or equal to max/end"
    ):
        validate_range(1.5, 0.5)

    # Invalid types
    with pytest.raises(TypeError, match="Value must be a number"):
        validate_range("0", 10)

    with pytest.raises(TypeError, match="Value must be a number"):
        validate_range(0, "10")


def test_validate_between_range():
    # Valid cases
    validate_between_range(5, 0, 10)
    validate_between_range(0, 0, 10)
    validate_between_range(10, 0, 10)
    validate_between_range(0.5, 0, 1)
    validate_between_range(5, None, 10)
    validate_between_range(5, 0, None)
    validate_between_range(None, 0, 10)

    # Invalid cases
    with pytest.raises(
        ValueError, match="Value must be greater than or equal to 0"
    ):
        validate_between_range(-1, 0, 10)

    with pytest.raises(
        ValueError, match="Value must be less than or equal to 10"
    ):
        validate_between_range(11, 0, 10)

    # Invalid types
    with pytest.raises(TypeError, match="Value must be a number"):
        validate_between_range("5", 0, 10)


def test_validate_number():
    # Valid numbers
    validate_number(0)
    validate_number(10)
    validate_number(-10)
    validate_number(0.5)
    validate_number(-0.5)

    # Invalid types
    with pytest.raises(TypeError, match="Value must be a number"):
        validate_number("0")

    with pytest.raises(TypeError, match="Value must be a number"):
        validate_number([1, 2, 3])

    with pytest.raises(TypeError, match="Value must be a number"):
        validate_number({"key": "value"})

    with pytest.raises(TypeError, match="Value must be a number"):
        validate_number(None)


def test_warn_js_safe_number():
    # Safe numbers
    with warnings.catch_warnings(record=True) as w:
        warn_js_safe_number(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
        assert len(w) == 0, "Unexpected warning raised for safe numbers"

    # Unsafe numbers
    with warnings.catch_warnings(record=True) as w:
        warn_js_safe_number(9007199254740992)  # MAX_SAFE_INTEGER + 1
        assert len(w) == 1
        assert issubclass(w[-1].category, UserWarning)
        assert "outside the range of safe integers" in str(w[-1].message)

    # Mixed safe and unsafe numbers
    with warnings.catch_warnings(record=True) as w:
        warn_js_safe_number(1, 9007199254740992, 2)
        assert len(w) == 1
        assert issubclass(w[-1].category, UserWarning)
        assert "outside the range of safe integers" in str(w[-1].message)

    # None values
    with warnings.catch_warnings(record=True) as w:
        warn_js_safe_number(None, 1, None, float("nan"))
        assert len(w) == 0, "Unexpected warning raised for None values"

    # Invalid types
    with warnings.catch_warnings(record=True) as w:
        warn_js_safe_number("0")
        assert len(w) == 0, "Unexpected warning raised for invalid types"
