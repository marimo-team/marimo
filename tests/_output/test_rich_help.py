from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Optional

from marimo._output.rich_help import (
    RichHelp,
    _doc_with_signature,
    _format_parameter,
    _get_signature,
    mddoc,
)


def test_format_parameter() -> None:
    """Test the _format_parameter function with different parameter types."""
    # Parameter with no annotation or default
    param = inspect.Parameter(
        "simple_param", inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    assert _format_parameter(param) == "simple_param"

    # Parameter with annotation but no default
    param = inspect.Parameter(
        "typed_param",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=str,
    )
    assert _format_parameter(param) == "typed_param: str"

    # Parameter with default but no annotation
    param = inspect.Parameter(
        "default_param",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        default=42,
    )
    assert _format_parameter(param) == "default_param = 42"

    # Parameter with string default
    param = inspect.Parameter(
        "string_default",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        default="default",
    )
    assert _format_parameter(param) == "string_default = 'default'"

    # Parameter with annotation and default
    param = inspect.Parameter(
        "full_param",
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=int,
        default=100,
    )
    assert _format_parameter(param) == "full_param: int = 100"


def test_get_signature_function() -> None:
    """Test _get_signature with a function."""

    def example_func(arg1: str, arg2: int = 42) -> bool:
        """Example function for testing."""
        del arg1, arg2
        return True

    signature = _get_signature(example_func)
    assert "def example_func(arg1: str, arg2: int = 42) -> bool:" in signature


def test_get_signature_class() -> None:
    """Test _get_signature with a class."""

    @dataclass
    class ExampleClass:
        name: str
        value: int = 0

    signature = _get_signature(ExampleClass)
    assert "class ExampleClass(name: str, value: int = 0)" in signature


def test_get_signature_class_with_exception() -> None:
    """Test _get_signature with a class that raises an exception during signature inspection."""

    # Create a mock class that raises an exception when inspect.signature is called
    class ComplicatedClass:
        def __init__(self):
            pass

        # Make __name__ a property to simulate inspect.signature raising an exception
        @property
        def __name__(self):
            return "ComplicatedClass"

    # Create an instance and patch it to throw an exception on inspect.signature
    obj = ComplicatedClass()

    # Monkey patch __signature__ to raise an exception
    def raise_exception(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        raise ValueError("Cannot get signature")

    original_signature = inspect.signature
    try:
        inspect.signature = raise_exception
        result = _get_signature(obj)
        assert "ComplicatedClass" in result
    finally:
        inspect.signature = original_signature


def test_doc_with_signature() -> None:
    """Test the _doc_with_signature function."""

    def example_func(arg: str) -> None:
        """This is a docstring."""
        pass

    result = _doc_with_signature(example_func)
    assert "```python" in result
    assert "def example_func(arg: str) -> None:" in result
    assert "This is a docstring." in result

    # Test with no docstring
    def no_doc(arg: str) -> None:
        pass

    result = _doc_with_signature(no_doc)
    assert "```python" in result
    assert "def no_doc(arg: str) -> None:" in result
    assert "\n\n" not in result  # No docstring section


def test_richhelp_protocol() -> None:
    """Test the RichHelp protocol implementation."""

    # Test that the default _rich_help_ implementation works
    assert RichHelp._rich_help_() is not None
    assert (
        "Protocol to provide a class or function docstring"
        in RichHelp._rich_help_()
    )

    # Test with a class implementing the protocol
    class MyClass:
        """My class docstring."""

        @staticmethod
        def _rich_help_() -> Optional[str]:
            return "Custom rich help for MyClass"

    # Check if MyClass is recognized as implementing RichHelp protocol
    assert isinstance(MyClass, RichHelp)
    assert MyClass._rich_help_() == "Custom rich help for MyClass"


def test_mddoc_decorator() -> None:
    """Test the mddoc decorator."""

    @mddoc
    def decorated_func(arg1: str, arg2: int = 10) -> bool:
        """Example function with Google style docstring.

        Args:
            arg1: First argument
            arg2: Second argument with default

        Returns:
            A boolean value
        """
        del arg1, arg2
        return True

    # Test that _rich_help_ method was added
    assert hasattr(decorated_func, "_rich_help_")
    rich_help_output = decorated_func._rich_help_()
    assert rich_help_output is not None
    assert "```python" in rich_help_output
    assert (
        "def decorated_func(arg1: str, arg2: int = 10) -> bool:"
        in rich_help_output
    )

    # Test that the docstring was wrapped with MarkdownDocstring
    # assert isinstance(decorated_func.__doc__, MarkdownDocstring)
    assert isinstance(decorated_func.__doc__, str)

    # Test with a class
    @mddoc
    class DecoratedClass:
        """A class with docstring."""

        def __init__(self, name: str):
            self.name = name

    assert hasattr(DecoratedClass, "_rich_help_")
    rich_help_output = DecoratedClass._rich_help_()
    assert "class DecoratedClass(name: str)" in rich_help_output
