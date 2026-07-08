# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import warnings

from marimo._utils.deprecated import deprecated


def test_calling_decorated_function_warns():
    @deprecated("use bar instead")
    def foo(x):
        return x * 2

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = foo(5)

    assert result == 10
    assert len(caught) == 1
    assert issubclass(caught[0].category, DeprecationWarning)
    assert str(caught[0].message) == "use bar instead"


def test_arguments_are_forwarded():
    @deprecated("gone")
    def add(a, b, c=0):
        return a + b + c

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert add(1, 2, c=3) == 6


def test_decorator_preserves_metadata():
    @deprecated("gone")
    def original():
        """my docstring"""

    assert original.__name__ == "original"
    assert original.__doc__ == "my docstring"


def test_no_warning_until_called():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @deprecated("gone")
        def fn():
            return 1

        # Decorating alone must not warn; only invocation does.
        assert caught == []
        fn()
        assert len(caught) == 1
