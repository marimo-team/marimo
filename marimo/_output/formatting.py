# Copyright 2024 Marimo. All rights reserved.
"""Formatting protocol

This module defines a protocol for implementing objects that can be displayed
using marimo's media viewer.

To register a formatter for a type, user have two options:
    1. Implement a method _mime_ on the class that takes an instance
       and returns a (mime, data) tuple (i.e., implement the protocol MIME)
    2. Register a formatter function that takes a value and returns
       a (mime, data) tuple.

The function get_formatter(value: T) can be used to obtain a function that
instantiates a (mime, data) tuple for a value, with registered formatters
taking precedence over the MIME protocol.
"""

from __future__ import annotations

import json
import traceback
from dataclasses import dataclass
from html import escape
from typing import Any, Callable, Optional, Tuple, Type, TypeVar, cast

from marimo import _loggers as loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.builder import h
from marimo._output.formatters.repr_formatters import maybe_get_repr_formatter
from marimo._output.formatters.utils import src_or_src_doc
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import flatten_string
from marimo._plugins.core.media import io_to_data_url
from marimo._plugins.stateless.json_output import json_output
from marimo._plugins.stateless.mime import mime_renderer
from marimo._plugins.stateless.plain_text import plain_text
from marimo._utils.methods import is_callable_method

T = TypeVar("T")

# we use Tuple instead of the builtin tuple for py3.8 compatibility
Formatter = Callable[[T], Tuple[KnownMimeType, str]]
FORMATTERS: dict[Type[Any], Formatter[Any]] = {}
OPINIONATED_FORMATTERS: dict[Type[Any], Formatter[Any]] = {}
LOGGER = loggers.marimo_logger()


def formatter(t: Type[Any]) -> Callable[[Formatter[T]], Formatter[T]]:
    """Register a formatter function for a type

    Decorator to register a custom formatter for a given type.

    For example, to register a formatter for a class Foo with a string
    attribute data:

    ```
    @formatter(Foo)
    def show_foo(foo: Foo) -> tuple[str, str]:
        return ("text/html", f"<p>{foo.data}</p>")
    ```
    """

    def register_format(f: Formatter[T]) -> Formatter[T]:
        FORMATTERS[t] = f
        return f

    return register_format


def opinionated_formatter(
    t: Type[Any],
) -> Callable[[Formatter[T]], Formatter[T]]:
    """Register an opinionated formatter function for a type

    Decorator to register a custom formatter for a given type.

    For example, to register a formatter for a class Foo with a string
    attribute data:

    ```
    @opinionated_formatter(Foo)
    def show_df(foo: Foo) -> tuple[str, str]:
        return table(foo)._mime_()
    ```
    """

    def register_format(f: Formatter[T]) -> Formatter[T]:
        OPINIONATED_FORMATTERS[t] = f
        return f

    return register_format


def get_formatter(
    obj: T,
    # Include opinionated formatters by default
    # (e.g., for pandas, polars, arrow, etc.)
    include_opinionated: bool = True,
) -> Optional[Formatter[T]]:
    from marimo._runtime.context import ContextNotInitializedError, get_context

    try:
        get_context()
    except ContextNotInitializedError:
        if not FORMATTERS:
            from marimo._output.formatters.formatters import (
                register_formatters,
            )

            # Install formatters when marimo is being used without
            # a kernel (eg, in a unit test or when run as a Python script)
            register_formatters()

    # Plain opts out of opinionated formatters
    if isinstance(obj, Plain):
        child_formatter = get_formatter(obj.child, include_opinionated=False)
        if child_formatter:

            def plain_formatter(obj: T) -> tuple[KnownMimeType, str]:
                assert child_formatter is not None
                return child_formatter(cast(Plain, obj).child)

            return plain_formatter

    # Display protocol has the highest precedence
    if is_callable_method(obj, "_display_"):

        def f_mime(obj: T) -> tuple[KnownMimeType, str]:
            displayable_object = obj._display_()  # type: ignore
            _f = get_formatter(displayable_object)
            if _f is not None:
                return _f(displayable_object)
            else:
                return as_html(displayable_object)._mime_()

        return f_mime

    # Formatters dict gets precedence
    if include_opinionated:
        if type(obj) in OPINIONATED_FORMATTERS:
            return OPINIONATED_FORMATTERS[type(obj)]

    if type(obj) in FORMATTERS:
        return FORMATTERS[type(obj)]
    elif any(isinstance(obj, t) for t in FORMATTERS.keys()):
        # we avoid using the walrus operator (matched_type := t) above
        # to keep compatibility with Python < 3.8
        for t in FORMATTERS.keys():
            if isinstance(obj, t):
                return FORMATTERS[t]

    # Check for the MIME protocol
    if is_callable_method(obj, "_mime_"):

        def f_mime(obj: T) -> tuple[KnownMimeType, str]:
            mime, data = obj._mime_()  # type: ignore
            # Data should ideally a string, but in case it's bytes,
            # we convert it to a data URL
            if isinstance(data, bytes):
                return (mime, io_to_data_url(data, mime) or "")  # type: ignore

            return (mime, data)  # type: ignore

        return f_mime

    return maybe_get_repr_formatter(obj)


@dataclass
class FormattedOutput:
    mimetype: KnownMimeType
    data: str
    traceback: Optional[str] = None
    exception: BaseException | None = None


def try_format(obj: Any, include_opinionated: bool = True) -> FormattedOutput:
    obj = "" if obj is None else obj
    if (
        formatter := get_formatter(
            obj, include_opinionated=include_opinionated
        )
    ) is not None:
        try:
            mimetype, data = formatter(obj)
            return FormattedOutput(mimetype=mimetype, data=data)
        except BaseException as e:  # noqa: E722
            # Catching base exception so we're robust to bugs in libraries
            return FormattedOutput(
                mimetype="text/plain",
                data="",
                traceback=traceback.format_exc(),
                exception=e,
            )

    from marimo._runtime.context import ContextNotInitializedError, get_context

    glbls = {}
    try:
        ctx = get_context()
    except ContextNotInitializedError:
        pass
    else:
        glbls = ctx.globals

    tb = None
    try:
        # convert the object to a string using the kernel globals;
        # some libraries like duckdb introspect globals() ...
        data = eval("str(obj)", glbls, {"obj": obj})
    except Exception:
        tb = traceback.format_exc()
        return FormattedOutput(
            mimetype="text/plain",
            data="",
            traceback=tb,
        )
    else:
        return (
            FormattedOutput(
                mimetype="text/html",
                data=plain_text(escape(data)).text,
                traceback=tb,
            )
            if data
            else FormattedOutput(
                mimetype="text/plain",
                data="",
                traceback=tb,
            )
        )


@mddoc
def as_html(value: object) -> Html:
    """Convert a value to HTML that can be embedded into markdown.

    This function returns an `Html` object representing `value`. Use it to
    embed values into Markdown or other HTML strings.

    Args:
        value: An object

    Returns:
        An `Html` object

    Example:
        ```python3
        import matplotlib.pyplot as plt
        plt.plot([1, 2])
        axis = plt.gca()
        mo.md(
            f\"\"\"
            Here is a plot:

            {mo.as_html(axis)}
            \"\"\"
        )
        ```
    """
    if isinstance(value, Html):
        return value

    formatter = get_formatter(value)
    if formatter is None:
        return Html(f"<span>{escape(str(value))}</span>")

    mimetype, data = formatter(value)
    return mime_to_html(mimetype, data)


def as_dom_node(value: object) -> Html:
    """
    Similar to as_html, but allows for string, int, float, and bool values
    to be passed through without being wrapped in an Html object.
    """
    if isinstance(value, (str, int, float, bool)):
        return Html(escape(str(value)))

    return as_html(value)


def mime_to_html(mimetype: KnownMimeType, data: Any) -> Html:
    if mimetype == "text/html":
        # Using `as_html` to embed multiline HTML content
        # into a multiline markdown string can break Python markdown's
        # markdown processor (even if it is working "as intended", it's
        # behavior is not what we want). If the markdown string is
        # indentend, and the HTML is interpolated with an f-string,
        # then only the first line of the interpolated HTML will be indented;
        # this breaks Python markdown. Unfortunately, we can't indiscriminately
        # flatten the HTML because whitespace matters for some elements,
        # like pre tags. So for now we leave it to the formatter functions
        # to choose whether or not to flatten their HTML
        return Html(data)
    elif mimetype == "text/plain":
        # Flatten the HTML text to avoid indentation issues
        # when interpolating into markdown/a multiline string
        return Html(flatten_string(f"<span>{escape(data)}</span>"))
    elif mimetype.startswith("image"):
        return Html(flatten_string(f'<img src="{data}" alt="" />'))
    elif mimetype == "application/json":
        return Html(
            flatten_string(json_output(json_data=json.loads(data)).text)
        )

    return mime_renderer(mimetype, data)


@mddoc
def plain(value: Any) -> Plain:
    """Wrap a value to indicate that it should be displayed without any opinionated formatting.

    This is the best way to opt out of marimo's default dataframe rendering.

    Example:
        ```python
        df = data.cars()
        mo.plain(df)
        ```

    Args:
        value: Any value
    """
    return Plain(value)


class Plain:
    """
    Wrapper around a value to indicate that it should be displayed
    without any opinionated formatting.
    """

    def __init__(self, child: Any):
        self.child = child


@mddoc
def iframe(html: str, *, width: str = "100%", height: str = "400px") -> Html:
    """Embed an HTML string in an iframe.

    Scripts by default are not executed using `mo.as_html` or `mo.Html`,
    so if you have a script tag (written as `<script></script>`),
    you can use `mo.iframe` for scripts to be executed.

    You may also want to use this function to display HTML content
    that may contain styles that could interfere with the rest of the
    page.

    Example:
        ```python
        html = "<h1>Hello, world!</h1>"
        mo.iframe(html)
        ```

    Args:
        html (str): An HTML string
        width (str): The width of the iframe
        height (str): The height of the iframe
    """

    return Html(
        flatten_string(
            h.iframe(
                **src_or_src_doc(html),
                onload="__resizeIframe(this)",
                width=width,
                height=height,
            )
        ),
    )
