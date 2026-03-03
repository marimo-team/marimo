# Copyright 2026 Marimo. All rights reserved.

from marimo._utils.methods import getcallable, is_callable_method


def test_getcallable() -> None:
    """Test the getcallable utility function."""

    class WithCallable:
        def my_method(self) -> str:
            return "called"

    class WithNonCallable:
        my_method = "not callable"

    class WithGetattr:
        def __getattr__(self, name: str) -> str:
            return f"attr_{name}"

    # Returns callable when attribute exists and is callable
    obj_callable = WithCallable()
    result = getcallable(obj_callable, "my_method")
    assert result is not None
    assert callable(result)
    assert result() == "called"

    # Returns None when attribute exists but is not callable
    obj_non_callable = WithNonCallable()
    result = getcallable(obj_non_callable, "my_method")
    assert result is None

    # Returns None when attribute doesn't exist
    result = getcallable(obj_callable, "nonexistent")
    assert result is None

    # Returns None for objects with __getattr__ returning non-callable
    obj_getattr = WithGetattr()
    assert hasattr(obj_getattr, "any_attr")  # hasattr returns True
    result = getcallable(obj_getattr, "any_attr")
    assert result is None


def test_is_callable_method() -> None:
    """Test the is_callable_method utility function."""

    class WithMethod:
        def my_method(self) -> str:
            return "called"

    class WithNonCallable:
        my_attr = "not callable"

    class WithGetattr:
        def __getattr__(self, name: str) -> str:
            return f"attr_{name}"

    # Returns True when attribute exists and is callable
    obj = WithMethod()
    assert is_callable_method(obj, "my_method") is True

    # Returns False when attribute exists but is not callable
    obj_non_callable = WithNonCallable()
    assert is_callable_method(obj_non_callable, "my_attr") is False

    # Returns False when attribute doesn't exist
    assert is_callable_method(obj, "nonexistent") is False

    # Returns False for objects with __getattr__ returning non-callable
    obj_getattr = WithGetattr()
    assert hasattr(obj_getattr, "any_attr")  # hasattr returns True
    assert is_callable_method(obj_getattr, "any_attr") is False
