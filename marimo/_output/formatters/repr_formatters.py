# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Callable, Optional, cast

from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.iframe import maybe_wrap_in_iframe
from marimo._plugins.core.media import io_to_data_url
from marimo._utils.methods import is_callable_method

_WIDGET_VIEW_KEY = "application/vnd.jupyter.widget-view+json"

MEDIA_MIME_PREFIXES = (
    "image/",
    "audio/",
    "video/",
    "application/pdf",
)


def _maybe_as_anywidget_html(
    obj: Any,
    contents: dict[str, Any],
) -> Optional[tuple[KnownMimeType, str]]:
    """If the mimebundle is for an anywidget, return ``text/html``.

    Converts ``application/vnd.jupyter.widget-view+json`` mimebundles
    into the same ``<marimo-anywidget>`` HTML that ``mo.ui.anywidget()``
    produces.  Works for:

    - Descriptor-based widgets (``MimeBundleDescriptor``) — ESM is
      read directly from the descriptor's ``_extra_state``.
    - ``AnyWidget`` subclasses wrapped in a delegating class — ESM
      info is looked up from the shared registry populated by
      ``init_marimo_widget``.

    Traditional (non-anywidget) jupyter widgets are left untouched so
    the frontend can show its error banner.
    """
    widget_view = contents.get(_WIDGET_VIEW_KEY)
    if not isinstance(widget_view, dict):
        return None
    model_id = widget_view.get("model_id")
    if not model_id:
        return None

    js_url, js_hash = _resolve_esm(obj)
    if not js_url:
        return None

    from marimo._plugins.core.web_component import build_ui_plugin

    inner = build_ui_plugin(
        component_name="marimo-anywidget",
        initial_value={"model_id": model_id},
        label=None,
        args={
            "js-url": js_url,
            "js-hash": js_hash,
        },
    )
    # Wrap in <marimo-ui-element> so the plugin gets proper lifecycle
    # management (remount on re-run via random-id change).
    html = (
        f"<marimo-ui-element object-id='{model_id}' "
        f"random-id='{model_id}'>"
        f"{inner}"
        f"</marimo-ui-element>"
    )
    return ("text/html", html)


def _resolve_esm(obj: Any) -> tuple[str, str]:
    """Find the ESM URL and hash for a descriptor-based anywidget.

    Reads ``_esm`` from the ``ReprMimeBundle._extra_state`` that the
    descriptor caches on the instance.

    Returns ``("", "")`` if the ESM cannot be found.
    """
    repr_mb = getattr(obj, "_repr_mimebundle_", None)
    extra_state = getattr(repr_mb, "_extra_state", None)
    if not isinstance(extra_state, dict):
        return ("", "")
    esm = extra_state.get("_esm")
    if not isinstance(esm, str) or not esm:
        return ("", "")

    import marimo._output.data.data as mo_data
    from marimo._utils.code import hash_code

    return mo_data.js(esm).url, hash_code(esm)


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
                contents: Any
                # Try to call _repr_mimebundle_ with include/exclude parameters
                if attr == "_repr_mimebundle_":
                    try:
                        contents = method(include=None, exclude=None)
                        # Check if we got an empty result and retry without params
                        if not contents:
                            contents = method()
                    except TypeError:
                        # If that fails, call the method without parameters
                        contents = method()

                    # Handle tuple return format: (data, metadata)
                    # According to Jupyter spec, _repr_mimebundle_ can return either:
                    # 1. A dict (just the data)
                    # 2. A tuple of (data_dict, metadata_dict)
                    if isinstance(contents, tuple) and len(contents) == 2:
                        contents, _metadata = cast(
                            tuple[dict[str, Any], dict[str, Any]], contents
                        )

                    # Convert binary or audio/video data to data URLs for web display
                    if isinstance(contents, dict):
                        for mime_key, data in list(contents.items()):
                            # image/*, audio/*, video/*, and application/pdf are common binary types
                            if mime_key.startswith(
                                MEDIA_MIME_PREFIXES
                            ) and isinstance(data, bytes):
                                data_url = io_to_data_url(data, mime_key)
                                if data_url:
                                    contents[mime_key] = data_url
                            elif (
                                mime_key.startswith(MEDIA_MIME_PREFIXES)
                                and isinstance(data, str)
                                and not data.startswith(
                                    ("data:", "http:", "https:", "<", "{")
                                )
                            ):
                                # Base64-encoded string (e.g. from
                                # IPython._repr_mimebundle_)
                                contents[mime_key] = (
                                    f"data:{mime_key};base64,{data}"
                                )

                    # If this is an anywidget descriptor-based widget,
                    # produce <marimo-anywidget> HTML (same as mo.ui.anywidget)
                    # instead of the raw mimebundle. Traditional jupyter
                    # widgets pass through as the mimebundle (error banner).
                    if isinstance(contents, dict):
                        anywidget_result = _maybe_as_anywidget_html(
                            obj, contents
                        )
                        if anywidget_result is not None:
                            return anywidget_result

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
