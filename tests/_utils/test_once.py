# Copyright 2025 Marimo. All rights reserved.
from typing import Any

import pytest

from marimo._utils.once import once


def test_once_basic_functionality() -> None:
    """Test that a function decorated with @once is called only once."""
    call_count = 0

    @once
    def increment() -> int:
        nonlocal call_count
        call_count += 1
        return call_count

    # First call should execute
    result1 = increment()
    assert result1 == 1
    assert call_count == 1

    # Subsequent calls should not execute
    result2 = increment()
    assert result2 is None  # Returns None on subsequent calls
    assert call_count == 1

    # Multiple calls should still not execute
    increment()
    increment()
    assert call_count == 1


def test_once_with_arguments() -> None:
    """Test that @once works with functions that take arguments."""
    call_count = 0
    last_args = None
    last_kwargs = None

    @once
    def test_func(a: int, b: str, c: int = 10) -> tuple[int, str, int]:
        nonlocal call_count, last_args, last_kwargs
        call_count += 1
        last_args = (a, b, c)
        return a, b, c

    # First call with arguments
    result1 = test_func(1, "hello", c=20)
    assert result1 == (1, "hello", 20)
    assert call_count == 1
    assert last_args == (1, "hello", 20)

    # Second call with different arguments - should not execute
    result2 = test_func(2, "world", c=30)
    assert result2 is None
    assert call_count == 1
    assert last_args == (1, "hello", 20)  # Should still be from first call


def test_once_with_return_value() -> None:
    """Test that @once preserves the return value from the first call."""

    @once
    def get_value() -> str:
        return "hello world"

    result1 = get_value()
    assert result1 == "hello world"

    result2 = get_value()
    assert result2 is None  # Subsequent calls return None


def test_once_with_side_effects() -> None:
    """Test that @once prevents side effects from happening multiple times."""
    side_effects = []

    @once
    def side_effect_func() -> None:
        side_effects.append("executed")

    side_effect_func()
    assert side_effects == ["executed"]

    side_effect_func()
    side_effect_func()
    assert side_effects == ["executed"]  # Should still be just one


def test_once_with_exception() -> None:
    """Test that @once handles exceptions properly."""
    call_count = 0

    @once
    def failing_func() -> None:
        nonlocal call_count
        call_count += 1
        raise ValueError("Test error")

    # First call should raise exception
    with pytest.raises(ValueError, match="Test error"):
        failing_func()
    assert call_count == 1

    # Subsequent calls should not execute (and not raise)
    result = failing_func()
    assert result is None
    assert call_count == 1


def test_once_on_class_method() -> None:
    """Test that @once works on class methods and is per-instance."""

    class TestClass:
        def __init__(self) -> None:
            self.call_count = 0

        @once
        def method(self) -> int:
            self.call_count += 1
            return self.call_count

    # Test first instance
    instance1 = TestClass()
    result1 = instance1.method()
    assert result1 == 1
    assert instance1.call_count == 1

    result2 = instance1.method()
    assert result2 is None
    assert instance1.call_count == 1

    # Test second instance - should be independent (per-instance behavior)
    instance2 = TestClass()
    result3 = instance2.method()
    assert result3 == 1  # Should execute because it's a different instance
    assert instance2.call_count == 1

    # Second instance subsequent call should be blocked
    result4 = instance2.method()
    assert result4 is None
    assert instance2.call_count == 1

    # First instance should still be blocked
    instance1.method()
    assert instance1.call_count == 1


def test_once_on_static_method() -> None:
    """Test that @once works on static methods."""
    call_count = 0

    class TestClass:
        @staticmethod
        @once
        def static_method() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

    result1 = TestClass.static_method()
    assert result1 == 1
    assert call_count == 1

    result2 = TestClass.static_method()
    assert result2 is None
    assert call_count == 1

    # Calling from different instances should still be blocked
    instance = TestClass()
    result3 = instance.static_method()
    assert result3 is None
    assert call_count == 1


def test_once_on_class_method_decorator() -> None:
    """Test that @once works with @classmethod."""
    call_count = 0

    class TestClass:
        @classmethod
        @once
        def class_method(cls) -> int:
            nonlocal call_count
            call_count += 1
            return call_count

    result1 = TestClass.class_method()
    assert result1 == 1
    assert call_count == 1

    result2 = TestClass.class_method()
    assert result2 is None
    assert call_count == 1


def test_once_preserves_function_metadata() -> None:
    """Test that @once preserves function name and docstring."""

    @once
    def documented_function() -> str:
        """This is a test function."""
        return "test"

    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "This is a test function."


def test_once_multiple_decorators() -> None:
    """Test that @once works with other decorators."""
    call_count = 0

    def another_decorator(func):
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return f"decorated: {func(*args, **kwargs)}"

        return wrapper

    @another_decorator
    @once
    def test_func() -> str:
        nonlocal call_count
        call_count += 1
        return "hello"

    result1 = test_func()
    assert result1 == "decorated: hello"
    assert call_count == 1

    result2 = test_func()
    assert result2 == "decorated: None"
    assert call_count == 1


def test_once_with_complex_return_types() -> None:
    """Test that @once works with complex return types."""

    @once
    def return_dict() -> dict[str, int]:
        return {"a": 1, "b": 2}

    @once
    def return_list() -> list[str]:
        return ["hello", "world"]

    result1 = return_dict()
    assert result1 == {"a": 1, "b": 2}

    result2 = return_dict()
    assert result2 is None

    result3 = return_list()
    assert result3 == ["hello", "world"]

    result4 = return_list()
    assert result4 is None


def test_once_thread_safety_simulation() -> None:
    """Test that @once behaves predictably in concurrent-like scenarios."""
    call_count = 0
    results = []

    @once
    def concurrent_func() -> int:
        nonlocal call_count
        call_count += 1
        return call_count

    # Simulate multiple "concurrent" calls
    for _ in range(10):
        result = concurrent_func()
        results.append(result)

    # Only first call should have executed
    assert call_count == 1
    assert results[0] == 1
    assert all(r is None for r in results[1:])


class OnceClassLevel:
    """Test class to demonstrate per-class behavior of @once."""

    def __init__(self) -> None:
        self.instance_call_count = 0

    @once
    def instance_method(self) -> str:
        self.instance_call_count += 1
        return f"instance_{self.instance_call_count}"


def test_once_class_level_behavior() -> None:
    """Test that @once on methods is per-instance, not per-class."""
    # Create multiple instances
    obj1 = OnceClassLevel()
    obj2 = OnceClassLevel()
    obj3 = OnceClassLevel()

    # Each instance should be able to call the method once
    result1 = obj1.instance_method()
    assert result1 == "instance_1"
    assert obj1.instance_call_count == 1

    # Each instance should be independent
    result2 = obj2.instance_method()
    assert result2 == "instance_1"
    assert obj2.instance_call_count == 1

    result3 = obj3.instance_method()
    assert result3 == "instance_1"
    assert obj3.instance_call_count == 1

    # Subsequent calls on same instances should return None
    assert obj1.instance_method() is None
    assert obj2.instance_method() is None
    assert obj3.instance_method() is None

    # Call counts should remain the same
    assert obj1.instance_call_count == 1
    assert obj2.instance_call_count == 1
    assert obj3.instance_call_count == 1


def test_once_inheritance() -> None:
    """Test that @once works correctly with inheritance."""

    class Parent:
        def __init__(self) -> None:
            self.parent_calls = 0

        @once
        def parent_method(self) -> str:
            self.parent_calls += 1
            return "parent"

    class Child(Parent):
        def __init__(self) -> None:
            super().__init__()
            self.child_calls = 0

        @once
        def child_method(self) -> str:
            self.child_calls += 1
            return "child"

    child = Child()

    # Test parent method
    assert child.parent_method() == "parent"
    assert child.parent_calls == 1
    assert child.parent_method() is None
    assert child.parent_calls == 1

    # Test child method
    assert child.child_method() == "child"
    assert child.child_calls == 1
    assert child.child_method() is None
    assert child.child_calls == 1


def test_once_memory_cleanup() -> None:
    """Test that @once properly cleans up memory with weak references."""
    import gc

    class TestClass:
        def __init__(self, value: str) -> None:
            self.value = value
            self.call_count = 0

        @once
        def method(self) -> str:
            self.call_count += 1
            return f"{self.value}_{self.call_count}"

    # Create instances and call methods
    instance1 = TestClass("test1")
    instance2 = TestClass("test2")

    result1 = instance1.method()
    result2 = instance2.method()

    assert result1 == "test1_1"
    assert result2 == "test2_1"

    # Delete instances
    del instance1
    del instance2

    # Force garbage collection
    gc.collect()

    # Create new instances with same values
    instance3 = TestClass("test1")
    instance4 = TestClass("test2")

    # These should work because old instances were cleaned up
    result3 = instance3.method()
    result4 = instance4.method()

    assert result3 == "test1_1"  # Should execute because it's a new instance
    assert result4 == "test2_1"  # Should execute because it's a new instance
