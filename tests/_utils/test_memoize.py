from __future__ import annotations

from typing import Any

from marimo._utils.memoize import memoize_last_value


def test_memoization_with_same_args() -> None:
    call_count = 0

    @memoize_last_value
    def test_func(x: int, y: int) -> int:
        nonlocal call_count
        call_count += 1
        return x + y

    # First call
    result1 = test_func(2, 3)
    assert result1 == 5
    assert call_count == 1

    # Second call with same args
    result2 = test_func(2, 3)
    assert result2 == 5
    assert call_count == 1  # Should not increase


def test_memoization_with_different_args() -> None:
    call_count = 0

    @memoize_last_value
    def test_func(x, y):
        nonlocal call_count
        call_count += 1
        return x + y

    result1 = test_func(2, 3)
    assert result1 == 5
    assert call_count == 1

    result2 = test_func(3, 4)
    assert result2 == 7
    assert call_count == 2


def test_memoization_with_kwargs() -> None:
    call_count = 0

    @memoize_last_value
    def test_func(x: int, y: int, z: int = 0) -> int:
        nonlocal call_count
        call_count += 1
        return x + y + z

    result1 = test_func(2, 3, z=1)
    assert result1 == 6
    assert call_count == 1

    result2 = test_func(2, 3, z=1)
    assert result2 == 6
    assert call_count == 1  # Should not increase

    result3 = test_func(2, 3, z=2)
    assert result3 == 7
    assert call_count == 2


def test_memoization_with_mutable_args() -> None:
    call_count = 0

    @memoize_last_value
    def test_func(x: list[int], y: int) -> list[int]:
        nonlocal call_count
        call_count += 1
        return x + [y]

    list1 = [1, 2, 3]
    result1 = test_func(list1, 4)
    assert result1 == [1, 2, 3, 4]
    assert call_count == 1

    # Modifying the list should not affect memoization
    list1.append(4)
    result2 = test_func(list1, 4)
    assert result2 == [1, 2, 3, 4]
    assert call_count == 1


def test_memoization_with_unhashable_kwargs() -> None:
    call_count = 0

    @memoize_last_value
    def test_func(**kwargs: Any) -> int:
        nonlocal call_count
        call_count += 1
        return sum(kwargs.values())  # type: ignore

    result1 = test_func(a=1, b=2, c=3)
    assert result1 == 6
    assert call_count == 1

    result2 = test_func(a=1, b=2, c=3)
    assert result2 == 6
    assert call_count == 1  # Should not increase

    result3 = test_func(a=1, b=2, c=3, d=4)
    assert result3 == 10
    assert call_count == 2


def test_memoization_on_class_methods() -> None:
    class TestClass:
        def __init__(self, v: int):
            self.id = v

        @memoize_last_value
        def test_method(self, x: int) -> int:
            return self.id * x

    obj1 = TestClass(2)
    obj2 = TestClass(3)

    # Test obj1
    result1 = obj1.test_method(5)
    assert result1 == 10  # 2 * 5

    # Same input for obj1, should use memoized result
    result2 = obj1.test_method(5)
    assert result2 == 10  # 2 * 5

    # Same input for obj2, should compute differently
    result3 = obj2.test_method(5)
    assert result3 == 15  # 3 * 5

    # Different input for obj1, should recompute
    result4 = obj1.test_method(7)
    assert result4 == 14  # 2 * 7

    # Original input for obj2, should use memoized result
    result5 = obj2.test_method(5)
    assert result5 == 15  # 3 * 5

    # Ensure outputs are not shared between instances
    assert obj1.test_method(10) != obj2.test_method(10)

    # Ensure memoization doesn't work across instances
    assert obj1.test_method.__func__ is obj2.test_method.__func__
    assert obj1.test_method.__self__ is not obj2.test_method.__self__
