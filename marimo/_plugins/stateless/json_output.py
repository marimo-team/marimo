# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import JSONType, build_stateless_plugin


def json_output(
    json_data: JSONType,
    name: Optional[str] = None,
    value_types: Optional[str] = None,
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
    }
    if name is not None:
        element_args["name"] = name

    if value_types is not None:
        element_args["value-types"] = value_types
    else:
        element_args["value-types"] = "python"

    return Html(
        build_stateless_plugin(
            component_name="marimo-json-output",
            args=element_args,
        )
    )
