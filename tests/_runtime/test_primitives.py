"""Tests for marimo._runtime.primitives module."""

import functools
from typing import Any

from marimo._runtime.primitives import is_pure_function


class TestWrappedFunctionHandling:
    """Test handling of wrapped functions (decorators) in is_pure_function."""

    def test_wrapped_function_follows_wrapped_object(self):
        """Test that is_pure_function follows __wrapped__ attribute to check the underlying function."""

        def external_function():
            """A function from external module."""
            return 42

        external_function.__module__ = "external_module"

        # Create a decorator that wraps the function
        def decorator(func):
            @functools.wraps(func)
            def wrapper():
                return func()

            return wrapper

        decorated_function = decorator(external_function)

        # Mock globals dict
        defs = {"decorated_function": decorated_function}
        cache = {}

        # Should follow the wrapped function and determine purity based on that
        result = is_pure_function(
            "decorated_function", decorated_function, defs, cache
        )

        # Should be True since the wrapped function is external
        assert result is True

    def test_nested_wrapped_functions(self):
        """Test handling of functions with multiple layers of wrapping."""

        def original_function():
            return "original"

        original_function.__module__ = "external_module"

        def decorator1(func: Any) -> Any:
            @functools.wraps(func)
            def wrapper1(*args: Any, **kwargs: Any):
                return func(*args, **kwargs)

            return wrapper1

        def decorator2(func: Any) -> Any:
            @functools.wraps(func)
            def wrapper2(*args: Any, **kwargs: Any):
                return func(*args, **kwargs)

            return wrapper2

        # Apply multiple decorators
        @decorator2
        @decorator1
        def nested_decorated():
            return original_function()

        defs = {"nested_decorated": nested_decorated}
        cache = {}

        # Should handle nested wrapping correctly
        result = is_pure_function(
            "nested_decorated", nested_decorated, defs, cache
        )
        assert isinstance(result, bool)

    def test_wrapped_attribute_is_none(self):
        """Test handling when __wrapped__ exists but is None."""

        def function_with_none_wrapped():
            return 42

        function_with_none_wrapped.__module__ = "external_module"

        # Set __wrapped__ to None
        function_with_none_wrapped.__wrapped__ = None

        defs = {"function_with_none_wrapped": function_with_none_wrapped}
        cache = {}

        # Should handle None __wrapped__ gracefully
        result = is_pure_function(
            "function_with_none_wrapped",
            function_with_none_wrapped,
            defs,
            cache,
        )
        assert result is True  # External function should be pure

    def test_main_module_wrapped_function(self):
        """Test wrapped function from __main__ module."""

        def internal_function():
            return 42

        internal_function.__module__ = "__main__"

        def decorator(func):
            @functools.wraps(func)
            def wrapper():
                return func()

            return wrapper

        decorated_function = decorator(internal_function)

        defs = {
            "decorated_function": decorated_function,
            "internal_function": internal_function,
        }
        cache = {}

        # Should follow wrapped function and check if it's pure
        result = is_pure_function(
            "decorated_function", decorated_function, defs, cache
        )

        # Should be True since the wrapped function is also pure (no external refs)
        assert result is True
