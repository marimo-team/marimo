# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import inspect

from marimo._ast.fast_stack import fast_stack


class TestFastStack:
    @staticmethod
    def test_returns_list_of_frame_info() -> None:
        result = fast_stack()
        assert isinstance(result, list)
        assert all(isinstance(frame, inspect.FrameInfo) for frame in result)

    @staticmethod
    def test_frame_info_has_expected_fields() -> None:
        result = fast_stack()
        assert len(result) > 0
        frame_info = result[0]
        assert hasattr(frame_info, "frame")
        assert hasattr(frame_info, "filename")
        assert hasattr(frame_info, "lineno")
        assert hasattr(frame_info, "function")

    @staticmethod
    def test_contains_caller_function_name() -> None:
        result = fast_stack()
        function_names = [f.function for f in result]
        # The calling test function should be in the stack
        assert "test_contains_caller_function_name" in function_names

    @staticmethod
    def test_contains_caller_filename() -> None:
        result = fast_stack()
        filenames = [f.filename for f in result]
        # At least one frame should be from this test file
        assert any("test_fast_stack.py" in f for f in filenames)

    @staticmethod
    def test_max_depth_limits_results() -> None:
        result_limited = fast_stack(max_depth=2)
        result_full = fast_stack()
        assert len(result_limited) <= 2
        assert len(result_limited) <= len(result_full)

    @staticmethod
    def test_max_depth_none_returns_full_stack() -> None:
        result = fast_stack(max_depth=None)
        assert len(result) > 0

    @staticmethod
    def test_max_depth_zero_returns_empty() -> None:
        result = fast_stack(max_depth=0)
        assert result == []

    @staticmethod
    def test_context_fields_are_none() -> None:
        # fast_stack does not load context (for performance)
        result = fast_stack()
        assert len(result) > 0
        for frame_info in result:
            assert frame_info.code_context is None
            assert frame_info.index is None

    @staticmethod
    def test_nested_function_call() -> None:
        def inner() -> list[inspect.FrameInfo]:
            return fast_stack()

        def outer() -> list[inspect.FrameInfo]:
            return inner()

        result = outer()
        function_names = [f.function for f in result]
        assert "inner" in function_names
        assert "outer" in function_names

    @staticmethod
    def test_line_numbers_are_positive() -> None:
        result = fast_stack()
        for frame_info in result:
            assert frame_info.lineno > 0
