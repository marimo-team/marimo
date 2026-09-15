# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._utils.data_uri import from_data_uri

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class LayoutConfig:
    # type of layout
    type: str
    # data for layout
    data: dict[str, Any]


def layout_config_to_data_uri(config: LayoutConfig) -> str:
    contents = json.dumps({"type": config.type, "data": config.data})
    encoded = base64.b64encode(contents.encode("utf-8")).decode("ascii")
    return f"data:application/json;base64,{encoded}"


def parse_layout_config(value: object, *, source: str) -> LayoutConfig | None:
    if not isinstance(value, dict):
        LOGGER.warning("Layout config %s must be an object", source)
        return None

    layout_type = value.get("type")
    layout_data = value.get("data")
    if not isinstance(layout_type, str) or not isinstance(layout_data, dict):
        LOGGER.warning(
            "Layout config %s must contain string `type` and object `data` fields",
            source,
        )
        return None

    return LayoutConfig(type=layout_type, data=layout_data)


def _parse_layout_config(
    contents: str | bytes, *, source: str
) -> LayoutConfig | None:
    try:
        value = json.loads(contents)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as error:
        LOGGER.warning("Failed to parse layout config %s: %s", source, error)
        return None
    return parse_layout_config(value, source=source)


def save_layout_config(
    directory: str | Path, app_name: str, config: LayoutConfig
) -> str:
    """
    Save the layout configuration to disk
    at the given directory.

    The layout is saved as a JSON file under
        <directory>/layouts/<app_name>.{type}.json
    This allows:
        - all layouts to be saved in the same directory
        - multiple layouts to be saved for the same app
        - multiple apps can live in the same directory

    Returns: the path to the layout file
    """
    # remove py extension
    app_name_without_ext = app_name.replace(".py", "")
    # relative file path
    filepath = f"layouts/{app_name_without_ext}.{config.type}.json"
    # full file path
    full_filepath = os.path.join(directory, filepath)
    # create directory if it doesn't exist
    os.makedirs(os.path.dirname(full_filepath), exist_ok=True)
    with open(full_filepath, "w", encoding="utf-8") as f:
        json.dump(config.__dict__, f, indent=2)
    return filepath


def read_layout_config(
    directory: str | Path, filename: str
) -> LayoutConfig | None:
    """
    Read the layout configuration from disk.

    Returns: the layout configuration
    """
    # Handle data URI
    if filename.startswith("data:"):
        try:
            _mime, data = from_data_uri(filename)
        except Exception as e:
            LOGGER.warning("Failed to decode data URI: %s", e)
            return None
        return _parse_layout_config(data, source="data URI")

    filepath = os.path.join(directory, filename)
    if not os.path.exists(filepath):
        LOGGER.warning("Layout file %s does not exist", filepath)
        return None
    if not filepath.endswith(".json"):
        LOGGER.warning("Layout file %s is not a JSON file", filepath)
        return None
    try:
        with open(filepath, encoding="utf-8") as f:
            contents = f.read()
    except (OSError, UnicodeError) as error:
        LOGGER.warning("Failed to read layout config %s: %s", filepath, error)
        return None
    return _parse_layout_config(contents, source=filepath)
