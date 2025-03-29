# Copyright 2025 Marimo. All rights reserved.
from __future__ import annotations

from json import loads
from typing import Any, Optional

from marimo._output.hypertext import Html
from marimo._output.rich_help import mddoc
from marimo._plugins.stateless import json_output


@mddoc
def json(
    data: str | dict[str, Any] | list[Any],
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
        data: JSON string or JSON-compatible Python object(s) to render
        label: optional text label for the tree

    Returns:
        Html: `Html` object
    """
    if not isinstance(data, (str, dict, list)):
        raise ValueError(
            "Argument `data` must be a str, dict, or list, "
            f"but got: {type(data)}"
        )

    if isinstance(data, str):
        try:
            data = loads(data)
        except ValueError as e:
            raise ValueError(
                "Argument `data` must be a valid JSON string, "
                + f"but got: {data}"
            ) from e

    return json_output.json_output(
        json_data=data,
        name=label,
        value_types="json",
    )
