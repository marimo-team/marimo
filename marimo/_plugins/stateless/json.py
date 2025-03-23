# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from json import loads
from typing import Optional

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.stateless import json_output


@mddoc
def json(
    data: str,
    label: Optional[str] = None,
) -> Html:
    """Render a JSON with tree.

    Example:
        ```python3
        mo.json(
            '["entry", "another entry", {"key": [0, 1, 2]}]',
            label="A JSON in tree.",
        )
        ```

    Args:
        data: JSON string to render
        label: optional text label for the tree

    Returns:
        Html: `Html` object
    """
    if not isinstance(data, str):
        raise ValueError(
            "Argument `data` must be a str, " + f"but got: {type(data)}"
        )

    return json_output.json_output(
        json_data=loads(data),
        name=label,
        value_types="json",
    )
