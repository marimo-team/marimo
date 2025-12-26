# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import html
import inspect as inspect_

from marimo._output.builder import h
from marimo._output.formatting import as_html
from marimo._output.hypertext import Html


class inspect(Html):
    """Inspect a Python object.

    Displays objects with their attributes, methods, and documentation
    in a rich HTML format. Useful for exploring objects that lack a rich repr.

    Args:
        obj: The object to inspect.
        help: Show full help text (otherwise just first paragraph).
        methods: Show methods.
        docs: Show documentation for attributes/methods.
        private: Show private attributes (starting with '_').
        dunder: Show dunder attributes (starting with '__').
        sort: Sort attributes alphabetically.
        all: Show all attributes (methods, private, and dunder).
        value: Show the object's value/repr.

    Returns:
        (Html): An `Html` object.

    Example:
        ```python
        mo.inspect(obj, methods=True)
        ```
    """

    def __init__(
        self,
        obj: object,
        *,
        help: bool = False,  # noqa: A002
        methods: bool = False,
        docs: bool = True,
        private: bool = False,
        dunder: bool = False,
        sort: bool = True,
        all: bool = False,  # noqa: A002
        value: bool = True,
    ) -> None:
        self._obj = obj
        if all:
            methods = True
            private = True
            dunder = True

        type_label, name = _get_object_title(obj)

        type_colors = {
            "class": (
                "background-color: var(--blue-3); color: var(--blue-11);"
            ),
            "function": (
                "background-color: var(--green-3); color: var(--green-11);"
            ),
            "method": (
                "background-color: var(--purple-3); color: var(--purple-11);"
            ),
            "module": (
                "background-color: var(--orange-3); color: var(--orange-11);"
            ),
            "instance": (
                "background-color: var(--crimson-3); color: var(--crimson-11);"
            ),
            "object": (
                "background-color: var(--slate-3); color: var(--slate-11);"
            ),
        }

        pill_style = type_colors.get(type_label, type_colors["object"])

        docstring = inspect_.getdoc(obj) if docs else None
        if docstring and not help:
            docstring = docstring.split("\n\n")[0]

        attributes = _get_filtered_attributes(obj, methods, private, dunder)
        if sort:
            attributes.sort(key=lambda x: x[0])

        header = h.div(
            [
                h.span(
                    html.escape(type_label),
                    style=(
                        pill_style + "padding: 2px 8px; "
                        "border-radius: 4px; "
                        "font-family: monospace; "
                        "font-size: 0.75rem; "
                        "font-weight: 600; "
                        "margin-right: 8px; "
                        "display: inline-block;"
                    ),
                ),
                h.span(
                    html.escape(name),
                    style=(
                        "font-family: monospace; "
                        "font-size: 0.875rem; "
                        "color: var(--slate-12);"
                    ),
                ),
            ],
            style=(
                "padding: 10px 12px 8px 12px; display: flex; align-items: center;"
            ),
        )

        main_content: list[str] = []

        # Add divider after header
        main_content.append(
            h.div(
                "",  # Empty string for divider line
                style=(
                    "height: 1px; "
                    "background-color: var(--slate-3); "
                    "margin: 0 12px 8px 12px;"
                ),
            )
        )

        if docstring:
            doc_style = (
                "color: var(--slate-11); "
                "margin: 0 12px 8px 12px; "
                "font-size: 0.75rem; "
                "font-family: monospace; "
                "padding: 0; "
                "white-space: pre-wrap;"
            )
            main_content.append(h.div(html.escape(docstring), style=doc_style))

        if value and not inspect_.isclass(obj) and not callable(obj):
            main_content.append(_render_value(obj))

        if callable(obj):
            sig = _get_signature(obj)
            if sig:
                if inspect_.isfunction(obj) or inspect_.ismethod(obj):
                    # For functions/methods, show the full definition
                    func_name = (
                        obj.__name__ if hasattr(obj, "__name__") else ""
                    )
                    prefix = (
                        "async def"
                        if inspect_.iscoroutinefunction(obj)
                        else "def"
                    )
                    main_content.append(
                        h.div(
                            h.span(
                                f"{prefix} {html.escape(func_name)}{html.escape(sig)}:"
                            ),
                            style=(
                                "font-family: monospace; "
                                "font-size: 0.875rem; "
                                "color: var(--slate-12); "
                                "margin: 0 12px 8px 12px;"
                            ),
                        )
                    )
                else:
                    # For other callables (classes, etc), just show the signature
                    main_content.append(
                        h.div(
                            h.pre(
                                html.escape(sig),
                                style="color: var(--slate-12); overflow-x: auto; margin: 0;",
                            ),
                            style=(
                                "background-color: var(--background); "
                                "border: 1px solid var(--slate-3); "
                                "border-radius: 4px; "
                                "padding: 8px 10px; "
                                "margin: 0 12px 8px 12px; "
                                "font-family: monospace; "
                                "font-size: 0.875rem;"
                            ),
                        )
                    )

        if attributes:
            table_rows = []
            for name, value, attr_type, error in attributes:
                table_rows.append(
                    _render_attribute_row(name, value, attr_type, error, docs)
                )

            main_content.append(
                h.div(
                    h.table(h.tbody(table_rows)),
                    style=(
                        "overflow-x: auto; font-size: 0.875rem; padding: 0 0 8px 0;"
                    ),
                )
            )

        super().__init__(
            h.div(
                [header] + main_content if main_content else [header],
                style=(
                    "border-radius: 6px; "
                    "overflow: hidden; "
                    "background-color: var(--slate-1); "
                    "display: inline-block; "
                    "min-width: 0; "
                    "max-width: 100%;"
                ),
            )
        )

    def _repr_md_(self) -> str:
        try:
            return repr(self._obj)
        except Exception:
            return self.text


def _get_object_title(obj: object) -> tuple[str, str]:
    """Returns (type_label, name) for the object."""
    if inspect_.isclass(obj):
        module = obj.__module__
        if module and module != "__builtin__":
            return ("class", f"{module}.{obj.__name__}")
        return ("class", obj.__name__)
    elif inspect_.isfunction(obj):
        name = obj.__name__ if hasattr(obj, "__name__") else "function"
        return ("function", name)
    elif inspect_.ismethod(obj):
        name = obj.__name__ if hasattr(obj, "__name__") else "method"
        return ("method", name)
    elif inspect_.ismodule(obj):
        return (
            "module",
            obj.__name__ if hasattr(obj, "__name__") else "module",
        )
    elif hasattr(obj, "__class__"):
        cls = obj.__class__
        module = cls.__module__
        if module and module != "__builtin__":
            return ("instance", f"{module}.{cls.__name__}")
        return ("instance", cls.__name__)
    else:
        return ("object", type(obj).__name__)


def _get_signature(obj: object) -> str | None:
    try:
        return str(inspect_.signature(obj))  # type: ignore
    except (ValueError, TypeError):
        return None


def _get_filtered_attributes(
    obj: object, methods: bool, private: bool, dunder: bool
) -> list[tuple[str, bool, str, Exception | None]]:
    attributes: list[tuple[str, bool, str, Exception | None]] = []

    try:
        all_attrs = dir(obj)
    except Exception:
        return attributes

    for name in all_attrs:
        if name.startswith("__") and not dunder:
            continue
        if name.startswith("_") and not name.startswith("__") and not private:
            continue

        try:
            value = getattr(obj, name)
            error = None
        except Exception as e:
            value = None
            error = e

        if error is not None:
            attr_type = "error"
        elif _is_property(obj, name):
            attr_type = "property"
        elif callable(value):
            if not methods:
                continue
            attr_type = "method"
        else:
            attr_type = "attribute"

        attributes.append((name, value, attr_type, error))

    return attributes


def _is_property(obj: object, name: str) -> bool:
    for cls in inspect_.getmro(type(obj)):
        if name in cls.__dict__ and isinstance(cls.__dict__[name], property):
            return True
    return False


def _render_value(obj: object) -> str:
    container_style = (
        "background-color: var(--background); "
        "border: 1px solid var(--slate-3); "
        "border-radius: 4px; "
        "padding: 8px 10px; "
        "margin: 0 12px 8px 12px; "
        "overflow-x: auto; "
        "overflow-y: hidden;"
    )

    # Try to get HTML representation
    try:
        html_obj = as_html(obj)
        _, data = html_obj._mime_()
        return h.div(data, style=container_style)
    except Exception:
        # Fall back to repr
        pass

    try:
        value_repr = html.escape(repr(obj))
    except Exception as e:
        value_repr = f"&lt;repr-error {html.escape(str(e))}&gt;"

    return h.div(
        h.pre(
            value_repr,
            style="color: var(--slate-12); white-space: pre; margin: 0; font-family: monospace; font-size: 0.875rem;",
        ),
        style=container_style,
    )


def _render_attribute_row(
    name: str,
    value: object,
    attr_type: str,
    error: Exception | None,
    docs: bool,
) -> str:
    name_style_base = (
        "padding: 2px 8px 2px 12px; "
        "vertical-align: top; "
        "text-align: right; "
        "font-family: monospace; "
        "font-size: 0.75rem; "
        "white-space: nowrap; "
        "line-height: 1.5; "
        "color: var(--slate-10);"
    )

    equals_style = (
        "padding: 2px 4px; "
        "color: var(--slate-9); "
        "vertical-align: top; "
        "font-family: monospace; "
        "font-size: 0.75rem; "
        "line-height: 1.5;"
    )

    if error is not None:
        name_style = name_style_base + " color: var(--red-11);"
        error_repr = f'<span style="color: var(--red-11); font-family: monospace; font-size: 0.75rem;">&lt;{type(error).__name__}: {html.escape(str(error))}&gt;</span>'
        return h.tr(
            [
                h.td(html.escape(name), style=name_style),
                h.td("=", style=equals_style),
                h.td(
                    error_repr,
                    style="color: var(--red-11); vertical-align: top; line-height: 1.5; padding: 2px 12px 2px 4px;",
                ),
            ]
        )
    elif attr_type == "method":
        name_style = name_style_base
        display = _format_method(name, value, docs)
        return h.tr(
            [
                h.td(html.escape(name), style=name_style),
                h.td("=", style=equals_style),
                h.td(
                    h.span(html.escape(display), style="white-space: pre;"),
                    style=(
                        "color: var(--slate-11); "
                        "font-family: monospace; "
                        "font-size: 0.75rem; "
                        "vertical-align: top; "
                        "line-height: 1.5; "
                        "padding: 2px 12px 2px 4px;"
                    ),
                ),
            ]
        )
    else:
        name_style = name_style_base
        if attr_type == "property":
            name_style += " font-style: italic;"
        value_html = _render_value_inline(value)
        return h.tr(
            [
                h.td(html.escape(name), style=name_style),
                h.td("=", style=equals_style),
                h.td(
                    value_html,
                    style="color: var(--foreground); vertical-align: top; line-height: 1.5; padding: 2px 12px 2px 4px;",
                ),
            ]
        )


def _format_method(name: str, method: object, docs: bool) -> str:
    try:
        sig = inspect_.signature(method)  # type: ignore
        if inspect_.iscoroutinefunction(method):
            display = f"async def {name}{sig}"
        else:
            display = f"def {name}{sig}"
    except Exception:
        display = f"def {name}(...)"

    if docs:
        doc = inspect_.getdoc(method)
        if doc:
            first_line = doc.split("\n")[0]
            if len(first_line) > 80:
                first_line = first_line[:77] + "..."
            display += f": {first_line}"

    return display


def _render_value_inline(value: object) -> str:
    if isinstance(value, str):
        # Colors from @textea/json-viewer string rendering
        # Light mode: #cb4b16, Dark mode: #dc9656
        return h.span(
            f'"{html.escape(value)}"',
            style="color: light-dark(#cb4b16, #dc9656); font-family: monospace; font-size: 0.75rem;",
        )

    if isinstance(value, (int, float, bool, type(None))):
        return h.span(
            html.escape(str(value)),
            style="font-family: monospace; font-size: 0.75rem;",
        )

    # Try to get HTML representation
    try:
        html_obj = as_html(value)
        _, data = html_obj._mime_()
        if isinstance(value, (dict, list, tuple)):
            return h.div(
                data, style="font-size: 0.75rem; display: inline-block;"
            )
        return h.span(data, style="display: inline-block;")
    except Exception:
        # Fall back to repr
        pass

    try:
        value_str = repr(value)
    except Exception as e:
        value_str = f"<repr-error {str(e)}>"

    if len(value_str) > 200:
        value_str = value_str[:197] + "..."

    return h.span(
        html.escape(value_str),
        style="font-family: monospace; font-size: 0.75rem;",
    )
