# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Optional

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.iframe import maybe_wrap_in_iframe
from marimo._plugins.core.media import io_to_data_url
from marimo._utils.methods import is_callable_method


def maybe_get_repr_formatter(
    obj: Any,
) -> Optional[Callable[[Any], tuple[KnownMimeType, str]]]:
    """
    Get a formatter that uses the object's _repr_ methods.
    """
    md_mime_types: list[KnownMimeType] = [
        "text/markdown",
        "text/latex",
    ]

    # Check for the misc _repr_ methods
    # Order dictates preference
    reprs: list[tuple[str, KnownMimeType]] = [
        ("_repr_html_", "text/html"),  # text/html is preferred first
        ("_repr_mimebundle_", "application/vnd.marimo+mimebundle"),
        ("_repr_svg_", "image/svg+xml"),
        ("_repr_json_", "application/json"),
        ("_repr_png_", "image/png"),
        ("_repr_jpeg_", "image/jpeg"),
        ("_repr_markdown_", "text/markdown"),
        ("_repr_latex_", "text/latex"),
        ("_repr_text_", "text/plain"),  # last
    ]
    has_possible_repr = any(is_callable_method(obj, attr) for attr, _ in reprs)
    if has_possible_repr:
        # If there is any match, we return a formatter that calls
        # all the possible _repr_ methods, since some can be implemented
        # but return None
        def f_repr(obj: Any) -> tuple[KnownMimeType, str]:
            for attr, mime_type in reprs:
                if not is_callable_method(obj, attr):
                    continue

                method = getattr(obj, attr)
                # Try to call _repr_mimebundle_ with include/exclude parameters
                if attr == "_repr_mimebundle_":
                    try:
                        contents = method(include=[], exclude=[])
                    except TypeError:
                        # If that fails, call the method without parameters
                        contents = method()
                    # Remove text/plain from the mimebundle if it's present
                    # since there are other representations available
                    # N.B. We cannot pass this as an argument to the method
                    # because this unfortunately could break some libraries
                    # (e.g. ibis)
                    if (
                        isinstance(contents, dict)
                        and "text/plain" in contents
                        and len(contents) > 1
                    ):
                        contents.pop("text/plain")
                    # Convert markdown/latex to text/html if text/html is
                    # not present
                    for md_mime_type in md_mime_types:
                        if (
                            "text/html" not in contents
                            and md_mime_type in contents
                        ):
                            from marimo._output.md import md

                            contents["text/html"] = md(
                                str(contents[md_mime_type])
                            ).text
                else:
                    contents = method()

                # If the method returns None, continue to the next method
                if contents is None:
                    continue

                # Handle the case where the contents are bytes
                if isinstance(contents, bytes):
                    # Data should ideally a string, but in case it's bytes,
                    # we convert it to a data URL
                    data_url = io_to_data_url(
                        contents, fallback_mime_type=mime_type
                    )
                    return (mime_type, data_url or "")

                # Handle markdown and latex
                if mime_type in md_mime_types:
                    from marimo._output.md import md

                    return ("text/html", md(contents or "").text)

                # Handle HTML with <script> tags:
                if mime_type == "text/html":
                    contents = maybe_wrap_in_iframe(contents)

                return (mime_type, contents)

            return ("text/html", "")

        return f_repr

    return None
