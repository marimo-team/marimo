# Copyright 2023 Marimo. All rights reserved.
import inspect
from typing import Any, Callable, Generic, Optional, Protocol, TypeVar, cast

from typing_extensions import runtime_checkable

from marimo._utils.format_signature import format_signature

_WRAP_WIDTH = 72


def _format_parameter(parameter: inspect.Parameter) -> str:
    annotation = (
        ""
        if parameter.annotation == inspect.Parameter.empty
        else ": " + cast(str, parameter.annotation)
    )
    default = (
        ""
        if parameter.default == inspect.Parameter.empty
        else f" = '{str(parameter.default)}'"
        if isinstance(parameter.default, str)
        else f" = {str(parameter.default)}"
    )
    return parameter.name + annotation + default


def _get_signature(obj: Any) -> str:
    name = cast(str, obj.__name__)
    try:
        signature = inspect.signature(obj)
    except Exception:
        # classes with fancy metaclasses, like TypedDict, can throw
        # an exception
        return name + ": " + str(type(obj))

    parameters = ", ".join(
        [
            _format_parameter(parameter)
            for parameter in signature.parameters.values()
        ]
    )
    if inspect.isclass(obj):
        signature_text = name + "(" + parameters + ")"
        return format_signature("class ", signature_text, width=_WRAP_WIDTH)
    else:
        return_annotation = (
            " -> " + signature.return_annotation
            if (
                signature.return_annotation != inspect.Signature.empty
                and signature.return_annotation
            )
            else ""
        ) + ":"
        signature_text = (
            name + "(" + parameters + ")" + cast(str, return_annotation)
        )
        return format_signature("def ", signature_text, width=_WRAP_WIDTH)


def _doc_with_signature(obj: Any) -> str:
    """Return docstring with its signature prepended."""
    signature = "```python\n" + _get_signature(obj) + "\n```"
    return (
        signature + "\n\n" + inspect.cleandoc(cast(str, obj.__doc__))
        if obj.__doc__ is not None
        else signature
    )


T = TypeVar("T", bound=Callable[..., Any])


@runtime_checkable
class RichHelp(Protocol, Generic[T]):
    """Protocol to provide a class or function docstring formatted as markdown.

    Implement the protocol by implementing a `_rich_help_` static method, which
    should render a Markdown string documenting the class. For example:

    ```python3
    class MyClass:
        \"\"\"**MyClass.**

        A class implementing the `RichHelp` protocol.
        \"\"\"

        @staticmethod
        def _rich_help_() -> Optional[str]:
            return MyClass.__doc__
    ```
    """

    @staticmethod
    def _rich_help_() -> Optional[str]:
        return _doc_with_signature(RichHelp)

    __call__: T


def mddoc(obj: T) -> T:
    """Adds a `_rich_help_` method to the passed in object.

    Returns `obj`, with modification to implement the `RichHelp` protocol.
    """
    rich_help = cast(RichHelp[T], obj)
    rich_help._rich_help_ = lambda: _doc_with_signature(  # type: ignore[method-assign]  # noqa: E501
        obj
    )
    # cast back to original type, so type-hinters provide helpful information
    return cast(T, rich_help)
