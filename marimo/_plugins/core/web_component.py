# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
import re
from html import escape, unescape
from typing import (
    TYPE_CHECKING,
    Mapping,
    Sequence,
    TypeVar,
    Union,
    cast,
)

if TYPE_CHECKING:
    import sys

    if sys.version_info < (3, 10):
        from typing_extensions import TypeAlias
    else:
        from typing import TypeAlias

    from typing import Optional

from marimo._output.md import _md
from marimo._output.mime import MIME
from marimo._plugins.core.json_encoder import WebComponentEncoder

JSONType: TypeAlias = Union[
    Mapping[str, "JSONType"],
    Sequence["JSONType"],
    str,
    int,
    float,
    bool,
    MIME,  # MIME is a JSONType since we have a custom JSONEncoder for it
    None,
]

S = TypeVar("S", bound=JSONType)


def _build_attr(name: str, value: JSONType) -> str:
    processed = escape(json.dumps(value, cls=WebComponentEncoder))
    # manual escapes for things html.escape doesn't escape
    #
    # - backslashes, when unescaped can lead to problems
    # when embedding in markdown
    # - dollar sign, when unescaped can incorrectly be recognized as
    # latex delimiter when embedding into markdown
    processed = processed.replace("\\", "&#92;").replace("$", "&#36;")
    return f"data-{name}='{processed}'"


def build_ui_plugin(
    component_name: str,
    initial_value: Optional[JSONType],
    label: Optional[str],
    args: dict[str, JSONType],
    slotted_html: str = "",
) -> str:
    """
    Build HTML for a UI (stateful) plugin.

    Args:
    ----
    component_name: tag name of the component
    initial_value: JSON-serializable initial value of the component
    label: markdown string that component may use a text label
    args: mapping from arg names to JSON-serializable value
    slotted_html: HTML to slot in the component

    Returns:
    -------
    HTML text for the component
    """
    if "initial-value" in args:
        raise ValueError("initial-value is a reserved argument.")
    if "label" in args:
        raise ValueError("label is a reserved argument.")

    attrs: list[str] = [_build_attr("initial-value", initial_value)]
    if label is not None and label:
        attrs.append(_build_attr("label", _md(label, size="sm").text))
    else:
        attrs.append(_build_attr("label", None))

    for name, value in args.items():
        if value is not None:
            attrs.append(_build_attr(name, value))

    return (
        f"<{component_name} {' '.join(attrs)}>"
        f"{slotted_html}"
        f"</{component_name}>"
    )


def build_stateless_plugin(
    component_name: str,
    args: dict[str, JSONType],
    slotted_html: str = "",
) -> str:
    """
    Build HTML for a stateless plugin.

    Args:
    ----
    component_name: tag name of the component
    args: mapping from arg names to JSON-serializable value
    slotted_html: HTML to slot in the component

    Returns:
    -------
    HTML text for the component
    """
    attrs = [_build_attr(name, value) for name, value in args.items()]
    return (
        f"<{component_name} {' '.join(attrs)}>"
        f"{slotted_html}"
        f"</{component_name}>"
    )


def parse_initial_value(text: str) -> JSONType:
    """Get initial value from HTML for a UI element."""
    match = re.search("data-initial-value='(.*?)'", text)
    if match is None:
        raise ValueError("Invalid component HTML: ", text)
    return cast(JSONType, json.loads(unescape(match.groups()[0])))
