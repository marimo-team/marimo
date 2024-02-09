# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Optional

from marimo._output.hypertext import Html
from marimo._plugins.core.web_component import JSONType, build_stateless_plugin


def json_output(json_data: JSONType, name: Optional[str] = None) -> Html:
    """Build a json output element.

    Args:
    -----
    json_data: JSON-serializable data to display
    name: optional text label

    Returns:
    --------
    A string of HTML for a JSON output element.
    """
    return Html(
        build_stateless_plugin(
            component_name="marimo-json-output",
            args=(
                {"json-data": json_data, "name": name}
                if name is not None
                else {"json-data": json_data}
            ),
        )
    )
