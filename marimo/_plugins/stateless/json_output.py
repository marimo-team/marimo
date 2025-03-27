# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional

from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import JSONType, build_stateless_plugin


def json_output(
    json_data: JSONType,
    name: Optional[str] = None,
    *,
    value_types: Literal["python", "json"] = "python",
) -> Html:
    """Build a json output element.

    Args:
    -----
    json_data: JSON-serializable data to display
    name: optional text label
    value_types: optional value types to display,
        e.g. "python" (default) or "json"

    Returns:
    --------
    A string of HTML for a JSON output element.
    """
    element_args = {
        "json-data": json_data,
        "value-types": value_types,
    }
    if name is not None:
        element_args["name"] = name

    return Html(
        build_stateless_plugin(
            component_name="marimo-json-output",
            args=element_args,
        )
    )
