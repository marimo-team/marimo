# Copyright 2023 Marimo. All rights reserved.
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

import inspect
import io
import json
import pprint
import traceback
import types
from dataclasses import dataclass
from html import escape
from typing import Any, Callable, Optional, Tuple, Type, TypeVar

from marimo import _loggers as loggers
from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._output.utils import flatten_string
from marimo._plugins.stateless.json_output import json_output

T = TypeVar("T")

# we use Tuple instead of the builtin tuple for py3.8 compatibility
Formatter = Callable[[T], Tuple[str, str]]
FORMATTERS: dict[Type[Any], Formatter[Any]] = {}
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


def get_formatter(obj: T) -> Optional[Formatter[T]]:
    from marimo._runtime.context import get_context

    if not get_context().initialized and not FORMATTERS:
        from marimo._output.formatters.formatters import register_formatters

        # Install formatters when marimo is being used without
        # a kernel (eg, in a unit test or when run as a Python script)
        register_formatters()

    if type(obj) in FORMATTERS:
        return FORMATTERS[type(obj)]
    elif any(isinstance(obj, t) for t in FORMATTERS.keys()):
        # we avoid using the walrus operator (matched_type := t) above
        # to keep compatibility with Python < 3.8
        for t in FORMATTERS.keys():
            if isinstance(obj, t):
                return FORMATTERS[t]
    elif hasattr(obj, "_mime_"):
        method = obj._mime_
        if inspect.isclass(obj) and not isinstance(method, (types.MethodType)):
            return None
        if callable(method):

            def f(obj: T) -> tuple[str, str]:
                return obj._mime_()  # type: ignore

            return f
    elif hasattr(obj, "_repr_html_"):
        method = obj._repr_html_
        if inspect.isclass(obj) and not isinstance(method, (types.MethodType)):
            return None
        if callable(method):

            def f(obj: T) -> tuple[str, str]:
                return ("text/html", obj._repr_html_())  # type: ignore

            return f
    return None


@dataclass
class FormattedOutput:
    mimetype: str
    data: str
    traceback: Optional[str] = None


def try_format(obj: Any) -> FormattedOutput:
    obj = "" if obj is None else obj
    if (formatter := get_formatter(obj)) is not None:
        try:
            mimetype, data = formatter(obj)
            return FormattedOutput(mimetype=mimetype, data=data)
        except Exception:  # noqa: E722
            return FormattedOutput(
                mimetype="text/plain",
                data="",
                traceback=traceback.format_exc(),
            )
    else:
        tmpio = io.StringIO()
        tb = None
        if isinstance(obj, str):
            tmpio.write(obj)
        else:
            try:
                pprint.pprint(obj, stream=tmpio)
            except Exception:  # noqa: E722
                tmpio.write("")
                tb = traceback.format_exc()
        tmpio.seek(0)
        return FormattedOutput(
            mimetype="text/plain",
            data=tmpio.read(),
            traceback=tb,
        )


@mddoc
def as_html(value: object) -> Html:
    """Convert a value to HTML that can be embedded into markdown

    This function returns an `Html` object representing `value`. Use it to
    embed values into Markdown or other HTML strings.

    **Example.**

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

    **Args.**

    - `value`: An object

    **Returns.**

    - An `Html` object
    """
    if isinstance(value, Html):
        return value

    formatter = get_formatter(value)
    if formatter is None:
        return Html(f"<span>{escape(str(value))}</span>")

    mimetype, data = formatter(value)
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
    else:
        raise ValueError(f"Unsupported mimetype {mimetype}")
