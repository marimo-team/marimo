# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._messaging.completion_option import CompletionOption


class TestCompletionOption:
    def test_initialization(self) -> None:
        # Test basic initialization
        option = CompletionOption(
            name="test_function",
            type="function",
            completion_info="test_function(arg1, arg2) -> None",
        )

        assert option.name == "test_function"
        assert option.type == "function"
        assert option.completion_info == "test_function(arg1, arg2) -> None"

    def test_initialization_without_completion_info(self) -> None:
        # Test initialization without completion_info
        option = CompletionOption(
            name="test_var",
            type="variable",
            completion_info=None,
        )

        assert option.name == "test_var"
        assert option.type == "variable"
        assert option.completion_info is None

    def test_post_init_strips_trailing_quotes(self) -> None:
        # Test that __post_init__ strips trailing quotes
        option1 = CompletionOption(
            name='test_string"',
            type="string",
            completion_info=None,
        )
        assert option1.name == "test_string"

        option2 = CompletionOption(
            name="test_string'",
            type="string",
            completion_info=None,
        )
        assert option2.name == "test_string"

        # Test with multiple quotes
        option3 = CompletionOption(
            name='test_string"""',
            type="string",
            completion_info=None,
        )
        assert option3.name == "test_string"

        # Test with no quotes
        option4 = CompletionOption(
            name="test_string",
            type="string",
            completion_info=None,
        )
        assert option4.name == "test_string"
